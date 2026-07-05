from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from models.enums import OCRSource


class PageDocument(BaseModel):
    job_id: str
    page: int
    image_path: str
    preprocessed_path: Optional[str] = None
    language: Optional[str] = None
    is_handwritten: bool = False
    ocr_source: OCRSource = OCRSource.UNKNOWN
    ocr_confidence: float = 0.0
    paddle_fallback_confidence: Optional[float] = None
    ocr_text: str = ""
    translated_text: Optional[str] = None
    status: str = "pending"
    processed_at: Optional[datetime] = None
