import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)

def get_dynamodb_resource():
    """
    Initializes and returns the boto3 DynamoDB resource using configuration settings.
    """
    session_params = {}
    if settings.AWS_ACCESS_KEY_ID:
        session_params["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
    if settings.AWS_SECRET_ACCESS_KEY:
        session_params["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    session = boto3.Session(**session_params)
    
    resource_params = {"region_name": settings.AWS_REGION}
    if settings.DYNAMODB_ENDPOINT_URL:
        resource_params["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
    elif settings.AWS_ENDPOINT_URL:
        resource_params["endpoint_url"] = settings.AWS_ENDPOINT_URL

    return session.resource("dynamodb", **resource_params)

def get_table():
    """
    Returns the DynamoDB Table resource.
    """
    db = get_dynamodb_resource()
    return db.Table(settings.DYNAMODB_TABLE)

def save_extraction(document_id: str, record: Dict[str, Any]) -> None:
    """
    Saves an extraction record to DynamoDB.
    Key: PK = DOC#<document_id>, SK = METADATA
    """
    table = get_table()
    pk = f"DOC#{document_id}"
    sk = "METADATA"
    
    item = {
        "PK": pk,
        "SK": sk,
        "document_id": document_id,
        "document_type": record.get("document_type"),
        "fields": record.get("fields", []),
        "raw_ocr_text": record.get("raw_ocr_text", ""),
        "processing_time_ms": record.get("processing_time_ms", 0),
        "s3_image_key": record.get("s3_image_key", ""),
        "created_at": record.get("created_at") or datetime.utcnow().isoformat() + "Z"
    }
    
    try:
        logger.info(f"Saving extraction record: PK={pk}, SK={sk}")
        table.put_item(Item=item)
    except ClientError as e:
        logger.error(f"Failed to save extraction record to DynamoDB: {e}")
        raise RuntimeError(f"DynamoDB save failed: {e}")

def save_correction(document_id: str, corrected_fields: List[Dict[str, Any]]) -> None:
    """
    Saves human-in-the-loop corrections to DynamoDB.
    Key: PK = DOC#<document_id>, SK = CORRECTION#<timestamp>
    """
    table = get_table()
    pk = f"DOC#{document_id}"
    timestamp = datetime.utcnow().isoformat() + "Z"
    sk = f"CORRECTION#{timestamp}"
    
    item = {
        "PK": pk,
        "SK": sk,
        "document_id": document_id,
        "corrected_fields": corrected_fields,
        "corrected_at": timestamp
    }
    
    try:
        logger.info(f"Saving correction record: PK={pk}, SK={sk}")
        table.put_item(Item=item)
    except ClientError as e:
        logger.error(f"Failed to save correction record to DynamoDB: {e}")
        raise RuntimeError(f"DynamoDB save correction failed: {e}")

def get_history(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retrieves the history of extractions from DynamoDB.
    Performs a Scan with a filter on SK = 'METADATA'.
    Returns items sorted by created_at descending.
    """
    table = get_table()
    
    try:
        logger.info("Scanning DynamoDB table for extraction history")
        response = table.scan(
            FilterExpression="SK = :sk_val",
            ExpressionAttributeValues={":sk_val": "METADATA"}
        )
        
        items = response.get("Items", [])
        
        # Paginate if needed (for v1 limit 50 is fine)
        while "LastEvaluatedKey" in response and len(items) < limit:
            response = table.scan(
                FilterExpression="SK = :sk_val",
                ExpressionAttributeValues={":sk_val": "METADATA"},
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))
            
        # Clean up the output and sort by created_at descending
        cleaned_items = []
        for item in items:
            cleaned_items.append({
                "document_id": item.get("document_id"),
                "document_type": item.get("document_type"),
                "fields": item.get("fields", []),
                "raw_ocr_text": item.get("raw_ocr_text", ""),
                "processing_time_ms": item.get("processing_time_ms", 0),
                "s3_image_key": item.get("s3_image_key", ""),
                "created_at": item.get("created_at")
            })
            
        cleaned_items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return cleaned_items[:limit]
        
    except ClientError as e:
        logger.error(f"Failed to scan history from DynamoDB: {e}")
        raise RuntimeError(f"DynamoDB history scan failed: {e}")

def get_stats() -> Dict[str, Any]:
    """
    Computes field-level and overall extraction accuracy based on human-in-the-loop corrections.
    Scans the table, groups items by document_id, locates the METADATA and latest CORRECTION
    for each doc, and evaluates mismatch rates.
    """
    table = get_table()
    
    try:
        logger.info("Scanning DynamoDB for computing accuracy statistics")
        response = table.scan()
        items = response.get("Items", [])
        
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
            
        # Group items by document_id
        docs: Dict[str, Dict[str, Any]] = {}
        for item in items:
            doc_id = item.get("document_id")
            if not doc_id:
                continue
                
            if doc_id not in docs:
                docs[doc_id] = {"metadata": None, "corrections": []}
                
            sk = item.get("SK", "")
            if sk == "METADATA":
                docs[doc_id]["metadata"] = item
            elif sk.startswith("CORRECTION#"):
                docs[doc_id]["corrections"].append(item)
                
        total_documents_processed = 0
        total_documents_corrected = 0
        
        field_stats: Dict[str, Dict[str, int]] = {} # e.g. {"card_number": {"correct": X, "total": Y}}
        
        for doc_id, data in docs.items():
            metadata = data["metadata"]
            corrections = data["corrections"]
            
            if not metadata:
                continue
                
            total_documents_processed += 1
            
            if not corrections:
                # No corrections made. We can't use this as benchmark data
                # since we don't know if it's correct or just unreviewed.
                # However, for stats, we track how many have corrections.
                continue
                
            total_documents_corrected += 1
            
            # Sort corrections by corrected_at to find the latest
            corrections.sort(key=lambda x: x.get("corrected_at", ""))
            latest_correction = corrections[-1]
            
            # Map corrected fields by name for easy lookup
            # The structure of corrected_fields is: list[{name, value}]
            corrected_fields_map = {
                f["name"]: f["value"] for f in latest_correction.get("corrected_fields", [])
            }
            
            # Compare original fields with corrected fields
            for orig_field in metadata.get("fields", []):
                name = orig_field.get("name")
                orig_val = orig_field.get("value")
                
                # Check if it was corrected
                if name in corrected_fields_map:
                    corr_val = corrected_fields_map[name]
                    
                    # Normalize comparison (convert to string, strip whitespace)
                    norm_orig = str(orig_val).strip() if orig_val is not None else ""
                    norm_corr = str(corr_val).strip() if corr_val is not None else ""
                    
                    is_correct = (norm_orig == norm_corr)
                    
                    if name not in field_stats:
                        field_stats[name] = {"correct": 0, "total": 0}
                        
                    field_stats[name]["total"] += 1
                    if is_correct:
                        field_stats[name]["correct"] += 1
                        
        # Format the stats output
        field_accuracy = []
        overall_correct = 0
        overall_total = 0
        
        for field_name, stats in field_stats.items():
            total = stats["total"]
            correct = stats["correct"]
            accuracy_pct = (correct / total * 100) if total > 0 else 100.0
            
            field_accuracy.append({
                "field_name": field_name,
                "accuracy_percentage": round(accuracy_pct, 2),
                "total_comparisons": total,
                "correct_extractions": correct
            })
            
            overall_correct += correct
            overall_total += total
            
        overall_accuracy_pct = (overall_correct / overall_total * 100) if overall_total > 0 else 100.0
        
        return {
            "total_documents_processed": total_documents_processed,
            "total_documents_reviewed": total_documents_corrected,
            "overall_accuracy_percentage": round(overall_accuracy_pct, 2),
            "field_accuracies": field_accuracy
        }
        
    except ClientError as e:
        logger.error(f"Failed to scan and calculate statistics from DynamoDB: {e}")
        raise RuntimeError(f"DynamoDB stats scan failed: {e}")
