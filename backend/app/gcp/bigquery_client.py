import os
import json
import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

# Try to import google-cloud-bigquery, if it fails, set a flag
try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
    GCP_BIGQUERY_AVAILABLE = True
except ImportError:
    GCP_BIGQUERY_AVAILABLE = False
    logger.warning("google-cloud-bigquery library is not installed. BigQuery client will operate in mock mode.")

# Local SQLite fallback path
MOCK_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".gcp_bigquery_mock.db"
)

class SQLiteFallback:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def get_conn(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extractions (
                document_id TEXT PRIMARY KEY,
                document_type TEXT,
                fields TEXT,
                raw_ocr_text TEXT,
                processing_time_ms INTEGER,
                s3_image_key TEXT,
                created_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT,
                corrected_fields TEXT,
                corrected_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_extraction(self, document_id: str, record: Dict[str, Any]) -> None:
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO extractions 
            (document_id, document_type, fields, raw_ocr_text, processing_time_ms, s3_image_key, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            record.get("document_type"),
            json.dumps(record.get("fields", [])),
            record.get("raw_ocr_text", ""),
            record.get("processing_time_ms", 0),
            record.get("s3_image_key", ""),
            record.get("created_at") or datetime.utcnow().isoformat() + "Z"
        ))
        conn.commit()
        conn.close()

    def save_correction(self, document_id: str, corrected_fields: List[Dict[str, Any]]) -> None:
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO corrections (document_id, corrected_fields, corrected_at)
            VALUES (?, ?, ?)
        """, (
            document_id,
            json.dumps(corrected_fields),
            datetime.utcnow().isoformat() + "Z"
        ))
        conn.commit()
        conn.close()

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self.get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM extractions ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()

        history = []
        for r in rows:
            history.append({
                "document_id": r["document_id"],
                "document_type": r["document_type"],
                "fields": json.loads(r["fields"]) if r["fields"] else [],
                "raw_ocr_text": r["raw_ocr_text"],
                "processing_time_ms": r["processing_time_ms"],
                "s3_image_key": r["s3_image_key"],
                "created_at": r["created_at"]
            })
        return history

    def get_stats_data(self) -> tuple:
        conn = self.get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM extractions")
        extractions = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM corrections ORDER BY corrected_at ASC")
        corrections = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return extractions, corrections

# Instantiate fallback
sqlite_fallback = SQLiteFallback(MOCK_DB_PATH)

def get_bq_client():
    if not GCP_BIGQUERY_AVAILABLE:
        return None
        
    try:
        # Resolve credentials
        if settings.GCP_CREDENTIALS_JSON:
            if os.path.exists(settings.GCP_CREDENTIALS_JSON):
                credentials = service_account.Credentials.from_service_account_file(settings.GCP_CREDENTIALS_JSON)
            else:
                cred_info = json.loads(settings.GCP_CREDENTIALS_JSON)
                credentials = service_account.Credentials.from_service_account_info(cred_info)
            return bigquery.Client(project=settings.GCP_PROJECT, credentials=credentials)
        else:
            return bigquery.Client(project=settings.GCP_PROJECT)
    except Exception as e:
        logger.warning(f"Failed to initialize real BigQuery client ({e}). BigQuery client will operate in mock mode.")
        return None

def ensure_bq_tables_exist(client):
    try:
        # Create dataset if not exists
        dataset_id = f"{client.project}.{settings.BIGQUERY_DATASET}"
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "US"
        try:
            client.get_dataset(dataset_id)
        except Exception:
            logger.info(f"Creating BigQuery dataset {dataset_id}")
            client.create_dataset(dataset, timeout=30)

        # Create extractions table if not exists
        table_id = f"{dataset_id}.{settings.BIGQUERY_TABLE}"
        schema = [
            bigquery.SchemaField("document_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("document_type", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("fields", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("raw_ocr_text", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("processing_time_ms", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("s3_image_key", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "STRING", mode="NULLABLE")
        ]
        table = bigquery.Table(table_id, schema=schema)
        try:
            client.get_table(table_id)
        except Exception:
            logger.info(f"Creating BigQuery table {table_id}")
            client.create_table(table, timeout=30)

        # Create corrections table if not exists
        corr_table_id = f"{dataset_id}.{settings.BIGQUERY_TABLE}_corrections"
        corr_schema = [
            bigquery.SchemaField("document_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("corrected_fields", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("corrected_at", "STRING", mode="NULLABLE")
        ]
        corr_table = bigquery.Table(corr_table_id, schema=corr_schema)
        try:
            client.get_table(corr_table_id)
        except Exception:
            logger.info(f"Creating BigQuery corrections table {corr_table_id}")
            client.create_table(corr_table, timeout=30)
            
    except Exception as e:
        logger.error(f"Error checking/creating BigQuery tables: {e}")

def save_extraction(document_id: str, record: Dict[str, Any]) -> None:
    client = get_bq_client()
    if client is not None:
        try:
            logger.info(f"Saving extraction to BigQuery for ID: {document_id}")
            ensure_bq_tables_exist(client)
            table_id = f"{client.project}.{settings.BIGQUERY_DATASET}.{settings.BIGQUERY_TABLE}"
            row_to_insert = {
                "document_id": document_id,
                "document_type": record.get("document_type"),
                "fields": json.dumps(record.get("fields", [])),
                "raw_ocr_text": record.get("raw_ocr_text", ""),
                "processing_time_ms": record.get("processing_time_ms", 0),
                "s3_image_key": record.get("s3_image_key", ""),
                "created_at": record.get("created_at") or datetime.utcnow().isoformat() + "Z"
            }
            errors = client.insert_rows_json(table_id, [row_to_insert])
            if not errors:
                return
            logger.error(f"BigQuery row insertion errors: {errors}. Falling back to SQLite.")
        except Exception as e:
            logger.error(f"BigQuery save extraction failed: {e}. Falling back to SQLite.")

    # SQLite Fallback
    sqlite_fallback.save_extraction(document_id, record)

def save_correction(document_id: str, corrected_fields: List[Dict[str, Any]]) -> None:
    client = get_bq_client()
    if client is not None:
        try:
            logger.info(f"Saving correction to BigQuery for ID: {document_id}")
            ensure_bq_tables_exist(client)
            table_id = f"{client.project}.{settings.BIGQUERY_DATASET}.{settings.BIGQUERY_TABLE}_corrections"
            row_to_insert = {
                "document_id": document_id,
                "corrected_fields": json.dumps(corrected_fields),
                "corrected_at": datetime.utcnow().isoformat() + "Z"
            }
            errors = client.insert_rows_json(table_id, [row_to_insert])
            if not errors:
                return
            logger.error(f"BigQuery correction insertion errors: {errors}. Falling back to SQLite.")
        except Exception as e:
            logger.error(f"BigQuery save correction failed: {e}. Falling back to SQLite.")

    # SQLite Fallback
    sqlite_fallback.save_correction(document_id, corrected_fields)

def get_history(limit: int = 50) -> List[Dict[str, Any]]:
    client = get_bq_client()
    if client is not None:
        try:
            logger.info(f"Fetching extraction history from BigQuery (limit={limit})")
            table_id = f"{client.project}.{settings.BIGQUERY_DATASET}.{settings.BIGQUERY_TABLE}"
            query = f"SELECT * FROM `{table_id}` ORDER BY created_at DESC LIMIT {limit}"
            query_job = client.query(query)
            rows = query_job.result()
            
            history = []
            for r in rows:
                fields_data = r.get("fields", "[]")
                try:
                    fields_list = json.loads(fields_data) if isinstance(fields_data, str) else fields_data
                except Exception:
                    fields_list = []
                history.append({
                    "document_id": r.get("document_id"),
                    "document_type": r.get("document_type"),
                    "fields": fields_list,
                    "raw_ocr_text": r.get("raw_ocr_text"),
                    "processing_time_ms": r.get("processing_time_ms"),
                    "s3_image_key": r.get("s3_image_key"),
                    "created_at": r.get("created_at")
                })
            return history
        except Exception as e:
            logger.error(f"BigQuery history query failed: {e}. Falling back to SQLite.")

    # SQLite Fallback
    return sqlite_fallback.get_history(limit)

def get_stats() -> Dict[str, Any]:
    client = get_bq_client()
    extractions = []
    corrections = []
    
    if client is not None:
        try:
            logger.info("Fetching stats data from BigQuery")
            dataset_ref = f"{client.project}.{settings.BIGQUERY_DATASET}"
            ext_table = f"{dataset_ref}.{settings.BIGQUERY_TABLE}"
            corr_table = f"{ext_table}_corrections"
            
            query_ext = f"SELECT * FROM `{ext_table}`"
            extractions = [dict(row) for row in client.query(query_ext).result()]
            
            query_corr = f"SELECT * FROM `{corr_table}` ORDER BY corrected_at ASC"
            corrections = [dict(row) for row in client.query(query_corr).result()]
        except Exception as e:
            logger.error(f"BigQuery stats fetch failed: {e}. Falling back to SQLite.")
            extractions, corrections = sqlite_fallback.get_stats_data()
    else:
        extractions, corrections = sqlite_fallback.get_stats_data()

    # Calculate stats in python
    return compute_stats_from_data(extractions, corrections)

def compute_stats_from_data(extractions: List[Dict[str, Any]], corrections: List[Dict[str, Any]]) -> Dict[str, Any]:
    docs = {}
    
    # Store extraction records
    for item in extractions:
        doc_id = item.get("document_id")
        if not doc_id:
            continue
        docs[doc_id] = {"metadata": item, "corrections": []}

    # Store correction records (group by doc_id)
    for item in corrections:
        doc_id = item.get("document_id")
        if not doc_id:
            continue
        if doc_id in docs:
            corr_fields = item.get("corrected_fields")
            if isinstance(corr_fields, str):
                try:
                    corr_fields = json.loads(corr_fields)
                except Exception:
                    corr_fields = []
            docs[doc_id]["corrections"].append({
                "corrected_fields": corr_fields,
                "corrected_at": item.get("corrected_at")
            })

    total_documents_processed = 0
    total_documents_corrected = 0
    field_stats = {}

    for doc_id, data in docs.items():
        metadata = data["metadata"]
        doc_corrections = data["corrections"]
        
        if not metadata:
            continue
            
        total_documents_processed += 1
        if not doc_corrections:
            continue
            
        total_documents_corrected += 1
        
        doc_corrections.sort(key=lambda x: x.get("corrected_at", ""))
        latest_correction = doc_corrections[-1]
        
        corrected_fields_map = {
            f["name"]: f["value"] for f in latest_correction.get("corrected_fields", [])
        }
        
        orig_fields = metadata.get("fields")
        if isinstance(orig_fields, str):
            try:
                orig_fields = json.loads(orig_fields)
            except Exception:
                orig_fields = []
                
        for orig_field in orig_fields:
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
