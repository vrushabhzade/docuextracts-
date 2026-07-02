from typing import List, Optional
from pydantic import BaseModel, Field

class AdmitCardSchema(BaseModel):
    candidate_name: str = Field(description="Full name of the candidate taking the exam")
    roll_number: str = Field(description="Roll number or registration number of the candidate")
    exam_name: str = Field(description="Name of the exam, e.g., CBSE Board, JEE, NEET, UPSC")
    exam_date: Optional[str] = Field(None, description="Date of the exam or first day of examinations")
    center_code: Optional[str] = Field(None, description="Exam center code or venue name")
    subjects: List[str] = Field(default_factory=list, description="List of subjects or papers the candidate is registered for")
