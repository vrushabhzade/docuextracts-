from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class FieldDetail(BaseModel):
    name: str = Field(..., description="The name of the extracted field")
    value: Any = Field(None, description="The extracted text or structured value")
    confidence: str = Field("low", description="Confidence level: high, medium, or low")
    bbox: Optional[List[int]] = Field(None, description="Bounding box coordinates [x, y, w, h] of the text in the image")

class ExtractionResponse(BaseModel):
    document_id: str
    document_type: str
    processed_image_preview: str = Field(..., description="Base64 encoded PNG image preview for before/after comparison")
    image_url: str = Field(..., description="S3 presigned URL for the original image")
    fields: List[FieldDetail] = Field(default_factory=list)
    raw_ocr_text: str
    processing_time_ms: int

class FieldCorrection(BaseModel):
    name: str
    value: Any

class CorrectionRequest(BaseModel):
    document_id: str
    corrected_fields: List[FieldCorrection]

class FieldAccuracyDetail(BaseModel):
    field_name: str
    accuracy_percentage: float
    total_comparisons: int
    correct_extractions: int

class StatsResponse(BaseModel):
    total_documents_processed: int
    total_documents_reviewed: int
    overall_accuracy_percentage: float
    field_accuracies: List[FieldAccuracyDetail]

class HistoryResponseItem(BaseModel):
    document_id: str
    document_type: str
    fields: List[Dict[str, Any]]
    raw_ocr_text: str
    processing_time_ms: int
    s3_image_key: str
    created_at: str
    image_url: Optional[str] = None

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    results: List[str]
