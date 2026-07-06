import os
import logging
from datetime import timedelta
from app.config import settings

logger = logging.getLogger(__name__)

# Try to import google-cloud-storage, if it fails, set a flag
try:
    from google.cloud import storage
    from google.oauth2 import service_account
    GCP_STORAGE_AVAILABLE = True
except ImportError:
    GCP_STORAGE_AVAILABLE = False
    logger.warning("google-cloud-storage library is not installed. GCS client will operate in mock mode.")

# Local filesystem storage path for fallback
MOCK_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".gcp_storage_mock"
)

def get_gcs_client():
    if not GCP_STORAGE_AVAILABLE:
        return None
        
    try:
        # Resolve credentials
        if settings.GCP_CREDENTIALS_JSON:
            if os.path.exists(settings.GCP_CREDENTIALS_JSON):
                # It's a file path
                credentials = service_account.Credentials.from_service_account_file(settings.GCP_CREDENTIALS_JSON)
            else:
                # It's a JSON string
                import json
                cred_info = json.loads(settings.GCP_CREDENTIALS_JSON)
                credentials = service_account.Credentials.from_service_account_info(cred_info)
            return storage.Client(project=settings.GCP_PROJECT, credentials=credentials)
        else:
            # Fallback to Application Default Credentials (ADC) or anonymous/local environment
            return storage.Client(project=settings.GCP_PROJECT)
    except Exception as e:
        logger.warning(f"Failed to initialize real GCS client ({e}). GCS client will operate in mock mode.")
        return None

def upload_image(document_id: str, image_bytes: bytes, filename: str) -> str:
    """
    Uploads document image bytes to the configured GCS bucket or local mock storage.
    """
    storage_key = f"documents/{document_id}/{filename}"
    client = get_gcs_client()
    
    if client is not None:
        try:
            logger.info(f"Uploading image to GCS: bucket={settings.GCS_BUCKET}, key={storage_key}")
            bucket = client.bucket(settings.GCS_BUCKET)
            blob = bucket.blob(storage_key)
            
            content_type = "image/png"
            if filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
                content_type = "image/jpeg"
                
            blob.upload_from_string(image_bytes, content_type=content_type)
            return storage_key
        except Exception as e:
            logger.error(f"GCS real upload failed: {e}. Falling back to mock storage.")
            
    # Mock Storage Fallback
    logger.info(f"[MOCK GCS] Saving image to mock GCS path: {storage_key}")
    target_path = os.path.join(MOCK_STORAGE_DIR, storage_key)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(image_bytes)
        
    return storage_key

def generate_presigned_url(storage_key: str, expiration: int = 3600) -> str:
    """
    Generates a signed URL to securely access a private GCS blob or mock file URL.
    """
    client = get_gcs_client()
    
    if client is not None:
        try:
            logger.info(f"Generating GCS signed URL for key={storage_key}")
            bucket = client.bucket(settings.GCS_BUCKET)
            blob = bucket.blob(storage_key)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expiration),
                method="GET"
            )
            return url
        except Exception as e:
            logger.error(f"GCS signed URL generation failed: {e}. Falling back to mock URL.")
            
    # Mock storage signed URL fallback (absolute URI path format)
    target_path = os.path.join(MOCK_STORAGE_DIR, storage_key)
    formatted_path = target_path.replace("\\", "/")
    return f"file:///{formatted_path}"
