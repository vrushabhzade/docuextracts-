import time
import uuid
import logging
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.preprocessing import preprocess_image
from app.ocr import perform_ocr
from app.extraction import extract_structured_data
from app.validation import validate_and_enrich_fields
from app.aws.s3_client import upload_image, generate_presigned_url
from app.aws.dynamodb_client import save_extraction, save_correction, get_history, get_stats
from app.models import ExtractionResponse, CorrectionRequest, StatsResponse, HistoryResponseItem, FieldDetail

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DocuExtract API",
    description="Structured Data Extraction Pipeline for Indian Documents",
    version="1.0.0"
)

# CORS Configuration
allowed_origins = [settings.ALLOWED_ORIGIN]
if "http://localhost:5173" not in allowed_origins:
    allowed_origins.append("http://localhost:5173")
# Also allow http://localhost:3000 just in case
if "http://localhost:3000" not in allowed_origins:
    allowed_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "environment": settings.ENVIRONMENT}

@app.post("/api/extract", response_model=ExtractionResponse)
async def extract_document(
    file: UploadFile = File(..., description="Image file of the document (JPG, PNG)"),
    document_type: str = Form(..., description="Document type: ration_card, admit_card, custom_form")
):
    """
    Uploads a document photo, runs it through the OpenCV preprocessor, 
    Tesseract OCR, Gemini extraction, rule validation, S3 storage, and DynamoDB logging.
    """
    start_time = time.time()
    document_id = str(uuid.uuid4())
    logger.info(f"Received extraction request. ID: {document_id}, Type: {document_type}")
    
    # 1. Read input file
    try:
        original_bytes = await file.read()
        if not original_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty image file received."
            )
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}"
        )
        
    # 2. Image Preprocessing (OpenCV)
    try:
        logger.info(f"[{document_id}] Preprocessing image...")
        processed_bytes, base64_preview = preprocess_image(original_bytes)
    except Exception as e:
        logger.error(f"[{document_id}] Preprocessing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Image preprocessing failed (possibly corrupt image): {str(e)}"
        )
        
    # 3. Multilingual OCR (Tesseract)
    try:
        logger.info(f"[{document_id}] Executing OCR...")
        ocr_words, raw_ocr_text = perform_ocr(processed_bytes)
    except Exception as e:
        logger.error(f"[{document_id}] OCR failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OCR engine execution failed: {str(e)}"
        )
        
    # 4. Schema-guided Extraction (Gemini 2.0 Flash)
    try:
        logger.info(f"[{document_id}] Extracting structured fields using Gemini...")
        extracted_fields = extract_structured_data(document_type, raw_ocr_text, ocr_words)
    except Exception as e:
        logger.error(f"[{document_id}] Gemini extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Structured extraction AI model failed: {str(e)}"
        )
        
    # 5. Rule-based Validation & Confidence Calculation
    try:
        logger.info(f"[{document_id}] Validating extracted fields...")
        validated_fields = validate_and_enrich_fields(extracted_fields)
    except Exception as e:
        logger.error(f"[{document_id}] Validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal validation rules engine failed: {str(e)}"
        )
        
    # 6. S3 Upload (Original and Processed preview)
    try:
        logger.info(f"[{document_id}] Uploading original and preprocessed images to S3...")
        # Upload original image
        original_s3_key = upload_image(document_id, original_bytes, file.filename or "original.png")
        # Upload processed image for archiving/audit
        _ = upload_image(document_id, processed_bytes, "processed.png")
    except Exception as e:
        logger.error(f"[{document_id}] S3 upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AWS S3 storage failed to save files: {str(e)}"
        )
        
    # 7. Generate presigned URL for frontend
    try:
        image_url = generate_presigned_url(original_s3_key, expiration=3600)
    except Exception as e:
        logger.error(f"[{document_id}] Presigned URL generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate secure URL access: {str(e)}"
        )
        
    # 8. Save Record to DynamoDB
    processing_time_ms = int((time.time() - start_time) * 1000)
    
    record = {
        "document_type": document_type,
        "fields": validated_fields,
        "raw_ocr_text": raw_ocr_text,
        "processing_time_ms": processing_time_ms,
        "s3_image_key": original_s3_key,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    try:
        logger.info(f"[{document_id}] Saving record to DynamoDB...")
        save_extraction(document_id, record)
    except Exception as e:
        logger.error(f"[{document_id}] DynamoDB save failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AWS DynamoDB failed to save document metadata: {str(e)}"
        )
        
    # Map back to field response model list
    response_fields = [FieldDetail(**f) for f in validated_fields]
    
    logger.info(f"[{document_id}] Extraction complete in {processing_time_ms}ms.")
    return ExtractionResponse(
        document_id=document_id,
        document_type=document_type,
        processed_image_preview=base64_preview,
        image_url=image_url,
        fields=response_fields,
        raw_ocr_text=raw_ocr_text,
        processing_time_ms=processing_time_ms
    )

@app.post("/api/extract/correct")
def correct_extraction(request: CorrectionRequest):
    """
    Saves human-in-the-loop corrections for a specific document extraction.
    Used to track validation errors and build the accuracy dataset.
    """
    logger.info(f"Received correction request for document: {request.document_id}")
    try:
        corrected_fields_list = [{"name": f.name, "value": f.value} for f in request.corrected_fields]
        save_correction(request.document_id, corrected_fields_list)
        return {"status": "success", "message": "Human corrections saved successfully."}
    except Exception as e:
        logger.error(f"Failed to save correction for document {request.document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AWS DynamoDB failed to save corrections: {str(e)}"
        )

@app.get("/api/history", response_model=List[HistoryResponseItem])
def get_extraction_history(limit: int = 50):
    """
    Retrieves the history of extractions from DynamoDB.
    Refreshes presigned S3 URLs so the images are viewable by the user.
    """
    logger.info(f"Fetching extraction history. Limit: {limit}")
    try:
        history = get_history(limit=limit)
        
        # Enrich each item with a fresh presigned S3 URL
        for item in history:
            s3_key = item.get("s3_image_key")
            if s3_key:
                try:
                    item["image_url"] = generate_presigned_url(s3_key, expiration=3600)
                except Exception as s3_err:
                    logger.warning(f"Could not generate presigned URL for key {s3_key}: {s3_err}")
                    item["image_url"] = ""
                    
        return [HistoryResponseItem(**item) for item in history]
    except Exception as e:
        logger.error(f"Failed to fetch extraction history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history logs: {str(e)}"
        )

@app.get("/api/stats", response_model=StatsResponse)
def get_extraction_statistics():
    """
    Computes field-level and overall system accuracy by comparing
    original extractions against human-corrected entries.
    """
    logger.info("Fetching extraction statistics")
    try:
        stats = get_stats()
        return StatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to calculate extraction stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate stats: {str(e)}"
        )
