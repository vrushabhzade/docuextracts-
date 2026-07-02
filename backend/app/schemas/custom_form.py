from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.base import KeyValueField

class CustomFormSchema(BaseModel):
    form_title: Optional[str] = Field(None, description="Title or header of the custom form or document")
    fields: List[KeyValueField] = Field(default_factory=list, description="Extracted key-value fields from the form")
