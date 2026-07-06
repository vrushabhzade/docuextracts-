import pytest
from unittest.mock import patch, MagicMock
from app.config import settings
from app import storage
from app import database
from app.gcp import gcs_client, bigquery_client

def test_storage_routing():
    # 1. Test AWS routing
    with patch("app.storage.aws_storage") as mock_aws, \
         patch("app.storage.gcp_storage") as mock_gcp, \
         patch("app.storage.settings") as mock_settings:
        
        mock_settings.STORAGE_PROVIDER = "aws"
        
        storage.upload_image("doc-1", b"bytes", "orig.png")
        mock_aws.upload_image.assert_called_once_with("doc-1", b"bytes", "orig.png")
        mock_gcp.upload_image.assert_not_called()
        
        mock_aws.reset_mock()
        mock_gcp.reset_mock()
        
        storage.generate_presigned_url("key-1", 100)
        mock_aws.generate_presigned_url.assert_called_once_with("key-1", 100)
        mock_gcp.generate_presigned_url.assert_not_called()

    # 2. Test GCP routing
    with patch("app.storage.aws_storage") as mock_aws, \
         patch("app.storage.gcp_storage") as mock_gcp, \
         patch("app.storage.settings") as mock_settings:
        
        mock_settings.STORAGE_PROVIDER = "gcp"
        
        storage.upload_image("doc-2", b"bytes2", "orig2.png")
        mock_gcp.upload_image.assert_called_once_with("doc-2", b"bytes2", "orig2.png")
        mock_aws.upload_image.assert_not_called()
        
        mock_aws.reset_mock()
        mock_gcp.reset_mock()
        
        storage.generate_presigned_url("key-2", 200)
        mock_gcp.generate_presigned_url.assert_called_once_with("key-2", 200)
        mock_aws.generate_presigned_url.assert_not_called()

def test_database_routing():
    # 1. Test AWS routing
    with patch("app.database.aws_db") as mock_aws, \
         patch("app.database.gcp_db") as mock_gcp, \
         patch("app.database.settings") as mock_settings:
        
        mock_settings.DATABASE_PROVIDER = "aws"
        
        database.save_extraction("doc-1", {"doc": "data"})
        mock_aws.save_extraction.assert_called_once_with("doc-1", {"doc": "data"})
        mock_gcp.save_extraction.assert_not_called()
        
        mock_aws.reset_mock()
        mock_gcp.reset_mock()
        
        database.save_correction("doc-1", [{"name": "n", "value": "v"}])
        mock_aws.save_correction.assert_called_once_with("doc-1", [{"name": "n", "value": "v"}])
        mock_gcp.save_correction.assert_not_called()

    # 2. Test GCP routing
    with patch("app.database.aws_db") as mock_aws, \
         patch("app.database.gcp_db") as mock_gcp, \
         patch("app.database.settings") as mock_settings:
        
        mock_settings.DATABASE_PROVIDER = "gcp"
        
        database.save_extraction("doc-2", {"doc": "data2"})
        mock_gcp.save_extraction.assert_called_once_with("doc-2", {"doc": "data2"})
        mock_aws.save_extraction.assert_not_called()
        
        mock_aws.reset_mock()
        mock_gcp.reset_mock()
        
        database.save_correction("doc-2", [{"name": "n2", "value": "v2"}])
        mock_gcp.save_correction.assert_called_once_with("doc-2", [{"name": "n2", "value": "v2"}])
        mock_aws.save_correction.assert_not_called()

def test_gcs_mock_fallback(tmp_path):
    mock_dir = tmp_path / "mock_gcs"
    with patch("app.gcp.gcs_client.MOCK_STORAGE_DIR", str(mock_dir)), \
         patch("app.gcp.gcs_client.get_gcs_client", return_value=None):
        
        key = gcs_client.upload_image("doc-123", b"testimage", "photo.png")
        assert key == "documents/doc-123/photo.png"
        
        file_path = mock_dir / "documents" / "doc-123" / "photo.png"
        assert file_path.exists()
        assert file_path.read_bytes() == b"testimage"
        
        url = gcs_client.generate_presigned_url(key)
        assert url.startswith("file://")
        assert "documents/doc-123/photo.png" in url

def test_bigquery_sqlite_fallback(tmp_path):
    db_file = tmp_path / "test_bq_mock.db"
    mock_sqlite = bigquery_client.SQLiteFallback(str(db_file))
    
    with patch("app.gcp.bigquery_client.sqlite_fallback", mock_sqlite), \
         patch("app.gcp.bigquery_client.get_bq_client", return_value=None):
        
        # 1. Save extraction
        record = {
            "document_type": "ration_card",
            "fields": [{"name": "card_number", "value": "MH123"}],
            "raw_ocr_text": "MH123 Ration Card",
            "processing_time_ms": 150,
            "s3_image_key": "path/to/img",
            "created_at": "2026-07-06T12:00:00Z"
        }
        bigquery_client.save_extraction("doc-999", record)
        
        # Check history
        history = bigquery_client.get_history(limit=5)
        assert len(history) == 1
        assert history[0]["document_id"] == "doc-999"
        assert history[0]["document_type"] == "ration_card"
        assert history[0]["fields"] == [{"name": "card_number", "value": "MH123"}]
        
        # 2. Save correction
        corr_fields = [{"name": "card_number", "value": "MH12345"}]
        bigquery_client.save_correction("doc-999", corr_fields)
        
        # 3. Calculate statistics
        stats = bigquery_client.get_stats()
        assert stats["total_documents_processed"] == 1
        assert stats["total_documents_reviewed"] == 1
        assert stats["overall_accuracy_percentage"] == 0.0
        
        # 4. Save correct correction
        corr_fields_correct = [{"name": "card_number", "value": "MH123"}]
        bigquery_client.save_correction("doc-999", corr_fields_correct)
        
        # Re-calc stats
        stats = bigquery_client.get_stats()
        assert stats["overall_accuracy_percentage"] == 100.0
