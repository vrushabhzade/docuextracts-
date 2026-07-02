import pytest
from unittest.mock import patch, MagicMock
import numpy as np
import cv2

# Import modules to test
from app.validation import (
    validate_verhoeff,
    validate_pincode,
    validate_phone_number,
    validate_date,
    validate_and_enrich_fields
)
from app.preprocessing import get_skew_angle, rotate_image
from app.ocr import perform_ocr
from app.extraction import find_bbox_and_confidence_for_value, extract_structured_data
from app.aws.secrets_client import get_gemini_api_key, clear_secrets_cache
from app.aws.s3_client import upload_image, generate_presigned_url
from app.aws.dynamodb_client import save_extraction, save_correction, get_stats

# ==============================================================================
# 1. Validation Tests (Verhoeff, Pincode, Phone, Date)
# ==============================================================================

def test_verhoeff_checksum():
    # Known valid Aadhaar numbers (Verhoeff checksum matches)
    # Aadhaar numbers must be 12 digits and have a valid Verhoeff check digit.
    # Standard valid test numbers:
    assert validate_verhoeff("366838848412") is True
    assert validate_verhoeff("471542455585") is True
    assert validate_verhoeff("755490407639") is True
    
    # Invalid numbers
    assert validate_verhoeff("123456789012") is False
    assert validate_verhoeff("000000000000") is False
    assert validate_verhoeff("abc") is False
    assert validate_verhoeff("") is False

def test_pincode_validation():
    # Valid pincodes
    assert validate_pincode("110001") is True
    assert validate_pincode("400001") is True
    assert validate_pincode(700019) is True # int check
    
    # Invalid pincodes
    assert validate_pincode("011001") is False # starts with 0
    assert validate_pincode("12345") is False  # 5 digits
    assert validate_pincode("1234567") is False # 7 digits
    assert validate_pincode("123a56") is False # alphabetic

def test_phone_number_validation():
    # Valid Indian mobile numbers (10 digits starting with 6-9)
    assert validate_phone_number("9876543210") is True
    assert validate_phone_number("+918765432109") is True # with country code
    assert validate_phone_number("07654321098") is True  # with zero prefix
    
    # Invalid numbers
    assert validate_phone_number("1234567890") is False # starts with 1
    assert validate_phone_number("987654321") is False  # too short
    assert validate_phone_number("98765432101") is False # too long

def test_date_validation():
    # Valid formats
    assert validate_date("15/08/1947") == (True, False)
    assert validate_date("1947-08-15") == (True, False)
    assert validate_date("15-08-1947") == (True, False)
    
    # Future dates (valid format, but flagged as future)
    assert validate_date("01/01/2050") == (True, True)
    
    # Invalid formats
    assert validate_date("2023/13/45") == (False, False)
    assert validate_date("not-a-date") == (False, False)

def test_validate_and_enrich_fields():
    test_fields = [
        {"name": "card_number", "value": "MH123", "ocr_confidence": 90.0, "bbox": [1, 2, 3, 4]},
        {"name": "aadhaar_number", "value": "366838848412", "ocr_confidence": 85.0, "bbox": [1, 2, 3, 4]},
        {"name": "pincode", "value": "110001", "ocr_confidence": 75.0, "bbox": [1, 2, 3, 4]},
        {"name": "mobile_phone", "value": "123456", "ocr_confidence": 95.0, "bbox": [1, 2, 3, 4]} # Fails validation
    ]
    
    enriched = validate_and_enrich_fields(test_fields)
    
    assert len(enriched) == 4
    assert enriched[0]["confidence"] == "high"    # Generic text, high OCR conf
    assert enriched[1]["confidence"] == "high"    # Valid Aadhaar, high OCR conf
    assert enriched[2]["confidence"] == "medium"  # Valid Pincode, medium OCR conf
    assert enriched[3]["confidence"] == "low"     # Invalid phone -> auto low

# ==============================================================================
# 2. Image Preprocessing Tests
# ==============================================================================

def test_preprocessing_straight_image():
    # Create a simple synthetic blank image (100x100 grayscale)
    img = np.ones((100, 100), dtype=np.uint8) * 255
    # Estimate skew angle
    angle = get_skew_angle(img)
    assert angle == 0.0
    
    # Test rotating image
    rotated = rotate_image(img, 0.0)
    assert rotated.shape == img.shape

# ==============================================================================
# 3. Extraction BBox Mapping Tests
# ==============================================================================

def test_bbox_and_confidence_mapping():
    ocr_words = [
        {"text": "Union", "confidence": 90.0, "bbox": [10, 20, 30, 40], "line_num": 1},
        {"text": "of", "confidence": 95.0, "bbox": [45, 20, 15, 40], "line_num": 1},
        {"text": "India", "confidence": 85.0, "bbox": [65, 20, 40, 40], "line_num": 1}
    ]
    
    bbox, conf = find_bbox_and_confidence_for_value("Union of India", ocr_words)
    assert bbox == [10, 20, 95, 40]  # combined boundaries
    assert conf == 90.0               # average of 90, 95, 85
    
    # Partial matching fallback
    bbox, conf = find_bbox_and_confidence_for_value("India", ocr_words)
    assert bbox == [65, 20, 40, 40]
    assert conf == 85.0

# ==============================================================================
# 4. AWS Client Mocks & Integration Tests
# ==============================================================================

@patch("app.aws.secrets_client.boto3.Session")
def test_secrets_client_production(mock_session_class):
    # Setup mocks
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session_class.return_value = mock_session
    mock_session.client.return_value = mock_client
    
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"GEMINI_API_KEY": "production_secret_key"}'
    }
    
    # Clear settings cache and override environment
    clear_secrets_cache()
    
    with patch("app.aws.secrets_client.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        mock_settings.AWS_REGION = "us-east-1"
        mock_settings.AWS_ACCESS_KEY_ID = "key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "secret"
        mock_settings.AWS_ENDPOINT_URL = None
        
        key = get_gemini_api_key()
        assert key == "production_secret_key"
        mock_client.get_secret_value.assert_called_once_with(SecretId="docuextract/gemini-key")

@patch("app.aws.s3_client.get_s3_client")
def test_s3_upload(mock_get_s3):
    mock_s3 = MagicMock()
    mock_get_s3.return_value = mock_s3
    
    with patch("app.aws.s3_client.settings") as mock_settings:
        mock_settings.S3_BUCKET = "test-bucket"
        
        key = upload_image("doc-123", b"imagebytes", "file.png")
        assert key == "documents/doc-123/file.png"
        mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="documents/doc-123/file.png",
            Body=b"imagebytes",
            ContentType="image/png"
        )

@patch("app.aws.dynamodb_client.get_table")
def test_dynamodb_save_extraction(mock_get_table):
    mock_table = MagicMock()
    mock_get_table.return_value = mock_table
    
    record = {
        "document_type": "ration_card",
        "fields": [],
        "raw_ocr_text": "Sample",
        "processing_time_ms": 100,
        "s3_image_key": "key",
        "created_at": "2026-07-01T12:00:00Z"
    }
    
    save_extraction("doc-123", record)
    mock_table.put_item.assert_called_once()
    saved_item = mock_table.put_item.call_args[1]["Item"]
    assert saved_item["PK"] == "DOC#doc-123"
    assert saved_item["SK"] == "METADATA"
