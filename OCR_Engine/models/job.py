from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from models.enums import JobStatus, DocumentType


class JobDocument(BaseModel):
    job_id: str
    file_name: str
    file_path: str
    file_size_bytes: int
    mime_type: str
    total_pages: int = 0
    processed_pages: int = 0
    failed_pages: int = 0
    handwritten_pages: int = 0
    paddle_pages: int = 0
    qwen_vl_pages: int = 0
    status: JobStatus = JobStatus.QUEUED
    doc_type: DocumentType = DocumentType.UNKNOWN
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
