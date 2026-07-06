import logging
from typing import List, Dict, Any
from app.config import settings
from app.aws import dynamodb_client as aws_db
from app.gcp import bigquery_client as gcp_db

logger = logging.getLogger(__name__)

def save_extraction(document_id: str, record: Dict[str, Any]) -> None:
    """
    Saves extraction metadata to the configured database provider (AWS DynamoDB or GCP BigQuery).
    """
    provider = settings.DATABASE_PROVIDER.lower()
    if provider == "gcp":
        logger.info(f"Routing save_extraction to GCP BigQuery for ID: {document_id}")
        gcp_db.save_extraction(document_id, record)
    else:
        logger.info(f"Routing save_extraction to AWS DynamoDB for ID: {document_id}")
        aws_db.save_extraction(document_id, record)

def save_correction(document_id: str, corrected_fields: List[Dict[str, Any]]) -> None:
    """
    Saves human corrections to the configured database provider (AWS DynamoDB or GCP BigQuery).
    """
    provider = settings.DATABASE_PROVIDER.lower()
    if provider == "gcp":
        logger.info(f"Routing save_correction to GCP BigQuery for ID: {document_id}")
        gcp_db.save_correction(document_id, corrected_fields)
    else:
        logger.info(f"Routing save_correction to AWS DynamoDB for ID: {document_id}")
        aws_db.save_correction(document_id, corrected_fields)

def get_history(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retrieves history logs from the configured database provider (AWS DynamoDB or GCP BigQuery).
    """
    provider = settings.DATABASE_PROVIDER.lower()
    if provider == "gcp":
        return gcp_db.get_history(limit)
    else:
        return aws_db.get_history(limit)

def get_stats() -> Dict[str, Any]:
    """
    Computes system and field accuracy statistics from the configured database provider.
    """
    provider = settings.DATABASE_PROVIDER.lower()
    if provider == "gcp":
        return gcp_db.get_stats()
    else:
        return aws_db.get_stats()
