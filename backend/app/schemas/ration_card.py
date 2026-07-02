from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.base import Member

class RationCardSchema(BaseModel):
    card_number: str = Field(description="The unique ration card number (sometimes starts with state letters)")
    head_of_household: str = Field(description="Name of the head of household")
    address: Optional[str] = Field(None, description="Complete address details printed on the card")
    category: Optional[str] = Field(None, description="Category of the ration card, e.g., APL, BPL, AAY, Priority Household (PHH)")
    members: List[Member] = Field(default_factory=list, description="List of family members registered on the card")
