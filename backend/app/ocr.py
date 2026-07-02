import io
import logging
from typing import List, Dict, Any, Tuple
from PIL import Image
import pytesseract
from pytesseract import TesseractNotFoundError, TesseractError

logger = logging.getLogger(__name__)

def perform_ocr(image_bytes: bytes) -> Tuple[List[Dict[str, Any]], str]:
    """
    Executes Tesseract OCR on preprocessed image bytes.
    Uses 'eng+hin+mar' languages.
    
    Returns:
        A tuple:
        - List of word details: [{"text": str, "confidence": float, "bbox": [x, y, w, h], "line_num": int}]
        - Reconstructed raw OCR text with line numbers (e.g. "Line 1: text\nLine 2: text...")
    """
    try:
        # Load image
        pil_img = Image.open(io.BytesIO(image_bytes))
        
        # Run Tesseract image_to_data to get bounding boxes and confidences
        logger.info("Executing pytesseract.image_to_data with lang='eng+hin+mar'")
        
        # Pytesseract config
        config = "--psm 3"  # Fully automatic page segmentation, but no OSD
        
        try:
            data = pytesseract.image_to_data(
                pil_img, 
                lang="eng+hin+mar", 
                config=config, 
                output_type=pytesseract.Output.DICT
            )
        except TesseractNotFoundError:
            raise RuntimeError(
                "Tesseract execution failed: Tesseract-OCR binary was not found on your system. "
                "Please verify Tesseract is installed and added to your PATH environment variable. "
                "On Debian/Ubuntu: apt-get install tesseract-ocr"
            )
        except TesseractError as te:
            # Handle case where specific language files are missing
            error_msg = str(te)
            if "Error opening data file" in error_msg or "Failed loading language" in error_msg:
                raise RuntimeError(
                    f"Tesseract language pack missing: {error_msg}. "
                    "Make sure you have installed 'hin' (Hindi) and 'mar' (Marathi) language packs. "
                    "On Debian/Ubuntu: apt-get install tesseract-ocr-hin tesseract-ocr-mar"
                )
            raise RuntimeError(f"Tesseract OCR failed: {error_msg}")
            
        words = []
        n_items = len(data["text"])
        
        # Structure to group words into lines for clean line-by-line text formatting
        # Key: (block_num, paragraph_num, line_num) -> Value: list of word indices
        line_groups: Dict[Tuple[int, int, int], List[int]] = {}
        
        for i in range(n_items):
            text = str(data["text"][i]).strip()
            conf = float(data["conf"][i])
            
            # conf = -1 means structural component, not actual word
            if conf == -1 or not text:
                continue
                
            # Store word info
            bbox = [
                int(data["left"][i]),
                int(data["top"][i]),
                int(data["width"][i]),
                int(data["height"][i])
            ]
            
            word_detail = {
                "text": text,
                "confidence": conf,
                "bbox": bbox,
                "line_num": int(data["line_num"][i])
            }
            words.append(word_detail)
            
            # Group by layout hierarchy to maintain proper line breaks
            line_key = (
                int(data["block_num"][i]), 
                int(data["par_num"][i]), 
                int(data["line_num"][i])
            )
            if line_key not in line_groups:
                line_groups[line_key] = []
            line_groups[line_key].append(i)
            
        # Reconstruct lines with line numbers for Gemini context prompt
        sorted_keys = sorted(line_groups.keys())
        raw_ocr_lines = []
        
        for idx, key in enumerate(sorted_keys, start=1):
            line_words = [data["text"][w_idx] for w_idx in line_groups[key] if str(data["text"][w_idx]).strip()]
            if line_words:
                line_text = " ".join(line_words)
                raw_ocr_lines.append(f"Line {idx}: {line_text}")
                
        raw_ocr_text_with_lines = "\n".join(raw_ocr_lines)
        
        logger.info(f"OCR complete. Found {len(words)} words in {len(raw_ocr_lines)} layout lines.")
        return words, raw_ocr_text_with_lines
        
    except Exception as e:
        logger.error(f"OCR execution failed: {e}")
        if isinstance(e, RuntimeError):
            raise e
        raise RuntimeError(f"OCR processing failed: {e}")
