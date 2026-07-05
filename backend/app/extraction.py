import logging
import json
from typing import List, Dict, Any, Tuple, Optional, Type
from pydantic import BaseModel
import google.generativeai as genai
from app.config import settings
from app.aws.secrets_client import get_gemini_api_key
from app.schemas.ration_card import RationCardSchema
from app.schemas.admit_card import AdmitCardSchema
from app.schemas.custom_form import CustomFormSchema

logger = logging.getLogger(__name__)

def get_schema_for_doc_type(document_type: str) -> Type[BaseModel]:
    """
    Returns the Pydantic schema class for a given document type.
    """
    schema_map = {
        "ration_card": RationCardSchema,
        "admit_card": AdmitCardSchema,
        "custom_form": CustomFormSchema
    }
    return schema_map.get(document_type, CustomFormSchema)

def flatten_pydantic_model(model_instance: BaseModel) -> List[Dict[str, Any]]:
    """
    Flattens a Pydantic model instance into a list of key-value dictionaries.
    Handles lists (like members or subjects) by generating indexed names.
    
    Returns:
        List of dicts: [{"name": str, "value": Any}]
    """
    flat_fields = []
    data_dict = model_instance.model_dump()
    
    for key, value in data_dict.items():
        if isinstance(value, list):
            # If it's a list of dicts (like members)
            if value and isinstance(value[0], dict):
                for idx, item in enumerate(value, start=1):
                    for sub_key, sub_value in item.items():
                        flat_fields.append({
                            "name": f"member_{idx}_{sub_key}",
                            "value": sub_value
                        })
            else:
                # If it's a simple list of primitives (like subjects)
                for idx, item in enumerate(value, start=1):
                    flat_fields.append({
                        "name": f"{key[:-1] if key.endswith('s') else key}_{idx}",
                        "value": item
                    })
        else:
            flat_fields.append({
                "name": key,
                "value": value
            })
            
    return flat_fields

def find_bbox_and_confidence_for_value(
    value: Any, 
    ocr_words: List[Dict[str, Any]]
) -> Tuple[Optional[List[int]], float]:
    """
    Finds the bounding box and calculates the average OCR confidence for an extracted value.
    Matches value tokens sequentially against the words detected in OCR.
    
    Returns:
        A tuple of (bbox [x, y, w, h], ocr_confidence [0-100])
    """
    if value is None:
        return None, 0.0
        
    value_str = str(value).strip().lower()
    if not value_str:
        return None, 0.0
        
    tokens = value_str.split()
    if not tokens:
        return None, 0.0
        
    n_words = len(ocr_words)
    
    # 1. Look for contiguous token matching
    for idx in range(n_words):
        if ocr_words[idx]["text"].lower() == tokens[0]:
            match_found = True
            match_indices = [idx]
            
            for offset, token in enumerate(tokens[1:], start=1):
                if (idx + offset >= n_words) or (ocr_words[idx + offset]["text"].lower() != token):
                    match_found = False
                    break
                match_indices.append(idx + offset)
                
            if match_found:
                # Calculate combined bounding box
                lefts = [ocr_words[i]["bbox"][0] for i in match_indices]
                tops = [ocr_words[i]["bbox"][1] for i in match_indices]
                rights = [ocr_words[i]["bbox"][0] + ocr_words[i]["bbox"][2] for i in match_indices]
                bottoms = [ocr_words[i]["bbox"][1] + ocr_words[i]["bbox"][3] for i in match_indices]
                
                x = min(lefts)
                y = min(tops)
                w = max(rights) - x
                h = max(bottoms) - y
                
                # Average OCR confidence
                avg_conf = sum(ocr_words[i]["confidence"] for i in match_indices) / len(match_indices)
                return [x, y, w, h], avg_conf
                
    # 2. Fallback: Check for partial matching or substring containment in single words
    for word in ocr_words:
        word_text = word["text"].lower()
        if value_str in word_text or word_text in value_str:
            return word["bbox"], word["confidence"]
            
    # Default fallback (could not resolve bbox)
    return None, 75.0

def clean_pydantic_schema_for_gemini(schema_class: Type[BaseModel]) -> genai.protos.Schema:
    """
    Converts a Pydantic model class into a google.generativeai.protos.Schema object
    that is fully compatible with the Gemini API, filtering out unsupported 
    fields like 'default' or Pydantic v2 'anyOf' union types.
    """
    json_schema = schema_class.model_json_schema()
    defs = json_schema.get("$defs", {})
    
    def resolve_ref(ref_path: str) -> dict:
        parts = ref_path.split("/")
        def_name = parts[-1]
        return defs.get(def_name, {})

    def recurse(schema_part: dict) -> dict:
        if not isinstance(schema_part, dict):
            return schema_part
            
        if "$ref" in schema_part:
            resolved = resolve_ref(schema_part["$ref"])
            return recurse(resolved)
            
        if "anyOf" in schema_part:
            non_null = [item for item in schema_part["anyOf"] if item.get("type") != "null"]
            if non_null:
                merged = non_null[0].copy()
                if "description" in schema_part:
                    merged["description"] = schema_part["description"]
                return recurse(merged)
            
        result = {}
        allowed_keys = {"type", "description", "properties", "items", "required", "enum"}
        for k, v in schema_part.items():
            if k in allowed_keys:
                target_key = "type_" if k == "type" else k
                
                if k == "type":
                    val = v.upper()
                else:
                    val = v

                if k == "properties" and isinstance(v, dict):
                    result[target_key] = {prop_name: recurse(prop_val) for prop_name, prop_val in v.items()}
                elif k == "items" and isinstance(v, dict):
                    result[target_key] = recurse(v)
                else:
                    result[target_key] = val
        return result

    cleaned_dict = recurse(json_schema)
    return genai.protos.Schema(cleaned_dict)

def clean_llm_json_response(text: str) -> str:
    """
    Cleans markdown formatting and extracts the first valid JSON object 
    (from the first '{' to the last '}') from the LLM response text.
    """
    text = text.strip()
    
    # Locate the first '{' and the last '}'
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx:end_idx + 1]
        
    # Fallback to standard stripping if no braces are found
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
        
    if text.endswith("```"):
        text = text[:-3]
        
    return text.strip()

def extract_structured_data(
    document_type: str, 
    raw_ocr_text: str, 
    ocr_words: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Extracts structured fields using Google Gemini or local Ollama.
    Enforces response schema matching the requested document type.
    Includes retry logic for validation failures.
    
    Returns:
        Tuple:
        - List of fields: [{"name": str, "value": Any, "ocr_confidence": float, "bbox": List[int]}]
        - Execution OCR word confidence list or metadata.
    """
    schema_class = get_schema_for_doc_type(document_type)
    parsed_data = None
    
    if settings.LLM_PROVIDER == "ollama":
        import requests
        
        # Format the schema description as JSON schema to feed to Ollama
        schema_desc = json.dumps(schema_class.model_json_schema(), indent=2)
        
        prompt = (
            f"You are a structured data extraction agent specializing in Indian documents.\n"
            f"Extract information from the OCR text below into a JSON object matching this schema:\n"
            f"{schema_desc}\n\n"
            f"Raw OCR Text:\n"
            f"{raw_ocr_text}\n\n"
            f"Extract values accurately. If a field cannot be found, return null.\n"
            f"Return ONLY a raw JSON object matching the schema. Do not include markdown formatting or explanations."
        )
        
        url = f"{settings.OLLAMA_API_URL.rstrip('/')}/api/generate"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }
        
        try:
            logger.info(f"Calling Ollama API ({settings.OLLAMA_MODEL}) at {url}")
            res = requests.post(url, json=payload, timeout=60)
            res.raise_for_status()
            response_text = res.json()["response"]
            parsed_data = schema_class.model_validate_json(clean_llm_json_response(response_text))
            logger.info("Successfully extracted and validated JSON matching Pydantic schema using Ollama on attempt 1.")
        except Exception as e:
            logger.warning(f"Initial Ollama extraction or parsing failed: {e}. Retrying with error correction...")
            
            # Retry with feedback
            retry_prompt = (
                f"You generated JSON that failed Pydantic validation with this error:\n"
                f"{str(e)}\n\n"
                f"Please correct the output, here is the source OCR text again:\n"
                f"{raw_ocr_text}\n\n"
                f"And here is the JSON schema:\n"
                f"{schema_desc}\n\n"
                f"Return only valid JSON matching the schema."
            )
            payload["prompt"] = retry_prompt
            try:
                res = requests.post(url, json=payload, timeout=60)
                res.raise_for_status()
                response_text = res.json()["response"]
                parsed_data = schema_class.model_validate_json(clean_llm_json_response(response_text))
                logger.info("Successfully extracted and validated JSON matching Pydantic schema using Ollama on attempt 2.")
            except Exception as retry_err:
                logger.error(f"Ollama extraction retry failed: {retry_err}")
                raise RuntimeError(f"Ollama local extraction failed: {retry_err}")
    else:
        # Verify API key
        api_key = get_gemini_api_key()
        if not api_key:
            raise RuntimeError("Gemini API Key is not configured. Please supply GEMINI_API_KEY.")
            
        genai.configure(api_key=api_key)
        gemini_schema = clean_pydantic_schema_for_gemini(schema_class)
        
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        
        # Prompt formulation
        prompt = (
            f"You are a structured data extraction agent specializing in Indian documents.\n"
            f"You will extract information from the following OCR text which includes line markers.\n"
            f"Format your response as a JSON object adhering exactly to the schema provided.\n"
            f"Extract values accurately. If a field cannot be found in the text, return null. "
            f"Do not invent or hallucinate values.\n\n"
            f"Raw OCR Text:\n"
            f"{raw_ocr_text}\n"
        )
        
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json",
            response_schema=gemini_schema,
            temperature=0.1
        )
        
        try:
            logger.info(f"Calling Gemini API for document_type={document_type}")
            response = model.generate_content(prompt, generation_config=generation_config)
            parsed_data = schema_class.model_validate_json(clean_llm_json_response(response.text))
            logger.info("Successfully extracted and parsed JSON matching Pydantic schema on attempt 1.")
        except Exception as e:
            logger.warning(f"Initial Gemini extraction or parsing failed: {e}. Retrying with error correction...")
            
            # Retry with feedback
            retry_prompt = (
                f"You previously generated an extraction that failed validation or parsing with the following error:\n"
                f"{str(e)}\n\n"
                f"Here is the source OCR text again:\n"
                f"{raw_ocr_text}\n\n"
                f"Please correct the error, extract the fields and output valid JSON matching the schema correctly."
            )
            try:
                response = model.generate_content(retry_prompt, generation_config=generation_config)
                parsed_data = schema_class.model_validate_json(clean_llm_json_response(response.text))
                logger.info("Successfully extracted and validated JSON on attempt 2.")
            except Exception as retry_err:
                logger.error(f"Gemini extraction retry failed: {retry_err}")
                raise RuntimeError(f"Generative AI extraction failed: {retry_err}")
            
    # Flatten parsed schema
    flat_extracted = flatten_pydantic_model(parsed_data)
    
    # Enriched fields list
    enriched_fields = []
    for field in flat_extracted:
        name = field["name"]
        val = field["value"]
        
        # Bounding box and Tesseract OCR confidence matching
        bbox, ocr_conf = find_bbox_and_confidence_for_value(val, ocr_words)
        
        enriched_fields.append({
            "name": name,
            "value": val,
            "ocr_confidence": ocr_conf,
            "bbox": bbox
        })
        
    return enriched_fields
