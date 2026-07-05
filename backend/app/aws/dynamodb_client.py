import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
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

def get_table_keys(table) -> Tuple[str, str]:
    """
    Retrieves the actual Partition Key (HASH) and Sort Key (RANGE) names from the table dynamically.
    Defaults to PK/SK if loading fails.
    """
    pk_name = "PK"
    sk_name = "Sk"
    try:
        table.load()
        for key in table.key_schema:
            if key["KeyType"] == "HASH":
                pk_name = key["AttributeName"]
            elif key["KeyType"] == "RANGE":
                sk_name = key["AttributeName"]
    except Exception as e:
        logger.warning(f"Could not load key schema from table, using defaults PK/SK: {e}")
    return pk_name, sk_name

def save_extraction(document_id: str, record: Dict[str, Any]) -> None:
    """
    Saves an extraction record to DynamoDB.
    """
    table = get_table()
    pk_name, sk_name = get_table_keys(table)
    
    pk = f"DOC#{document_id}"
    sk = "METADATA"
    
    item = {
        pk_name: pk,
        sk_name: sk,
        "document_id": document_id,
        "document_type": record.get("document_type"),
        "fields": record.get("fields", []),
        "raw_ocr_text": record.get("raw_ocr_text", ""),
        "processing_time_ms": record.get("processing_time_ms", 0),
        "s3_image_key": record.get("s3_image_key", ""),
        "created_at": record.get("created_at") or datetime.utcnow().isoformat() + "Z"
    }
    
    try:
        logger.info(f"Saving extraction record: {pk_name}={pk}, {sk_name}={sk}")
        table.put_item(Item=item)
    except ClientError as e:
        logger.error(f"Failed to save extraction record to DynamoDB: {e}")
        raise RuntimeError(f"DynamoDB save failed: {e}")

def save_correction(document_id: str, corrected_fields: List[Dict[str, Any]]) -> None:
    """
    Saves human-in-the-loop corrections to DynamoDB.
    """
    table = get_table()
    pk_name, sk_name = get_table_keys(table)
    
    pk = f"DOC#{document_id}"
    timestamp = datetime.utcnow().isoformat() + "Z"
    sk = f"CORRECTION#{timestamp}"
    
    item = {
        pk_name: pk,
        sk_name: sk,
        "document_id": document_id,
        "corrected_fields": corrected_fields,
        "corrected_at": timestamp
    }
    
    try:
        logger.info(f"Saving correction record: {pk_name}={pk}, {sk_name}={sk}")
        table.put_item(Item=item)
    except ClientError as e:
        logger.error(f"Failed to save correction record to DynamoDB: {e}")
        raise RuntimeError(f"DynamoDB save correction failed: {e}")

def get_history(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retrieves the history of extractions from DynamoDB.
    """
    table = get_table()
    pk_name, sk_name = get_table_keys(table)
    
    try:
        logger.info("Scanning DynamoDB table for extraction history")
        response = table.scan(
            FilterExpression=f"{sk_name} = :sk_val",
            ExpressionAttributeValues={":sk_val": "METADATA"}
        )
        
        items = response.get("Items", [])
        
        while "LastEvaluatedKey" in response and len(items) < limit:
            response = table.scan(
                FilterExpression=f"{sk_name} = :sk_val",
                ExpressionAttributeValues={":sk_val": "METADATA"},
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))
            
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
    """
    table = get_table()
    pk_name, sk_name = get_table_keys(table)
    
    try:
        logger.info("Scanning DynamoDB for computing accuracy statistics")
        response = table.scan()
        items = response.get("Items", [])
        
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
            
        docs: Dict[str, Dict[str, Any]] = {}
        for item in items:
            doc_id = item.get("document_id")
            if not doc_id:
                continue
                
            if doc_id not in docs:
                docs[doc_id] = {"metadata": None, "corrections": []}
                
            sk = item.get(sk_name, "")
            if sk == "METADATA":
                docs[doc_id]["metadata"] = item
            elif sk.startswith("CORRECTION#"):
                docs[doc_id]["corrections"].append(item)
                
        total_documents_processed = 0
        total_documents_corrected = 0
        
        field_stats: Dict[str, Dict[str, int]] = {}
        
        for doc_id, data in docs.items():
            metadata = data["metadata"]
            corrections = data["corrections"]
            
            if not metadata:
                continue
                
            total_documents_processed += 1
            if not corrections:
                continue
                
            total_documents_corrected += 1
            
            corrections.sort(key=lambda x: x.get("corrected_at", ""))
            latest_correction = corrections[-1]
            
            corrected_fields_map = {
                f["name"]: f["value"] for f in latest_correction.get("corrected_fields", [])
            }
            
            for orig_field in metadata.get("fields", []):
                name = orig_field.get("name")
                orig_val = orig_field.get("value")
                
                if name in corrected_fields_map:
                    corr_val = corrected_fields_map[name]
                    
                    norm_orig = str(orig_val).strip() if orig_val is not None else ""
                    norm_corr = str(corr_val).strip() if corr_val is not None else ""
                    
                    is_correct = (norm_orig == norm_corr)
                    
                    if name not in field_stats:
                        field_stats[name] = {"correct": 0, "total": 0}
                        
                    field_stats[name]["total"] += 1
                    if is_correct:
                        field_stats[name]["correct"] += 1
                        
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
