import logging
from app.config import settings
from app.aws import s3_client as aws_storage
from app.gcp import gcs_client as gcp_storage

logger = logging.getLogger(__name__)

def upload_image(document_id: str, image_bytes: bytes, filename: str) -> str:
    """
    Uploads image using the configured storage provider (AWS S3 or GCP Cloud Storage).
    """
    provider = settings.STORAGE_PROVIDER.lower()
    if provider == "gcp":
        logger.info(f"Routing upload_image to GCP Cloud Storage for ID: {document_id}")
        return gcp_storage.upload_image(document_id, image_bytes, filename)
    else:
        logger.info(f"Routing upload_image to AWS S3 for ID: {document_id}")
        return aws_storage.upload_image(document_id, image_bytes, filename)

def generate_presigned_url(storage_key: str, expiration: int = 3600) -> str:
    """
    Generates a secure/signed URL for the image using the configured storage provider.
    """
    provider = settings.STORAGE_PROVIDER.lower()
    if provider == "gcp":
        return gcp_storage.generate_presigned_url(storage_key, expiration)
    else:
        return aws_storage.generate_presigned_url(storage_key, expiration)
