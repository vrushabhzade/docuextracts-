from typing import Optional
from pydantic import BaseModel, Field

class Member(BaseModel):
    name: str = Field(description="Full name of the family member as printed on the card")
    aadhaar_number: Optional[str] = Field(None, description="Aadhaar number of the family member (usually 12 digits)")
    relationship: Optional[str] = Field(None, description="Relationship with the head of household")
    age: Optional[str] = Field(None, description="Age or date of birth of the family member")

class KeyValueField(BaseModel):
    key: str = Field(description="The name or label of the field")
    value: Optional[str] = Field(None, description="The extracted text value of the field")
