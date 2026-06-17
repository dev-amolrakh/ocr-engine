from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from models.enums import DocumentType


class ExtractionDocument(BaseModel):
    job_id: str
    doc_type: DocumentType = DocumentType.UNKNOWN
    extracted_data: dict = Field(default_factory=dict)
    confidence: float = 0.0
    validated: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    extracted_at: Optional[datetime] = None
