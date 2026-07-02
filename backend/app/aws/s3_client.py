import logging
import boto3
from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)

def get_s3_client():
    """
    Initializes and returns the boto3 S3 client using configuration settings.
    """
    session_params = {}
    if settings.AWS_ACCESS_KEY_ID:
        session_params["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
    if settings.AWS_SECRET_ACCESS_KEY:
        session_params["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    session = boto3.Session(**session_params)
    
    client_params = {"region_name": settings.AWS_REGION}
    if settings.AWS_ENDPOINT_URL:
        # Can use AWS_ENDPOINT_URL for local testing or custom endpoints
        client_params["endpoint_url"] = settings.AWS_ENDPOINT_URL

    return session.client("s3", **client_params)

def upload_image(document_id: str, image_bytes: bytes, filename: str) -> str:
    """
    Uploads document image bytes to the configured S3 bucket.
    
    Args:
        document_id: The unique ID of the document.
        image_bytes: The raw image file bytes.
        filename: The name of the file (e.g. 'original.png', 'processed.png').
        
    Returns:
        The S3 key where the file was uploaded.
    """
    s3_client = get_s3_client()
    s3_key = f"documents/{document_id}/{filename}"
    
    try:
        logger.info(f"Uploading image to S3: bucket={settings.S3_BUCKET}, key={s3_key}")
        
        # Determine content type based on file extension
        content_type = "image/png"
        if filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
            
        s3_client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=s3_key,
            Body=image_bytes,
            ContentType=content_type
        )
        return s3_key
    except ClientError as e:
        logger.error(f"Failed to upload image to S3 (key={s3_key}): {e}")
        raise RuntimeError(f"Failed to store image in S3: {e}")

def generate_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """
    Generates a presigned URL to securely access a private S3 object.
    
    Args:
        s3_key: The S3 key of the object.
        expiration: Time in seconds before the presigned URL expires (default 1 hour).
        
    Returns:
        A secure presigned GET URL.
    """
    s3_client = get_s3_client()
    
    try:
        logger.info(f"Generating presigned URL for key={s3_key}")
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": s3_key
            },
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL for key={s3_key}: {e}")
        raise RuntimeError(f"Failed to generate S3 presigned URL: {e}")
