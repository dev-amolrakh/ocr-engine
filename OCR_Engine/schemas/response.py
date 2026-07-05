from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    job_id: str
    status: str
    total_pages: int
    poll_url: str


class BulkUploadResponse(BaseModel):
    jobs: list[UploadResponse]
    total_files: int


class OCRStats(BaseModel):
    paddle_pages: int = 0
    qwen_vl_pages: int = 0
    handwritten_pages: int = 0


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total_pages: int
    processed_pages: int
    failed_pages: int = 0
    progress_pct: float
    doc_type: str
    ocr_stats: OCRStats
    uploaded_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class OCRSummary(BaseModel):
    total_pages: int
    languages_detected: list[str]
    pages_translated: int
    paddle_pages: int
    qwen_vl_pages: int
    handwritten_pages: int


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    doc_type: str
    extracted_data: dict = Field(default_factory=dict)
    confidence: float = 0.0
    validated: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    ocr_summary: OCRSummary


class PageResponse(BaseModel):
    job_id: str
    page: int
    language: Optional[str] = None
    is_handwritten: bool = False
    ocr_source: str = "unknown"
    ocr_confidence: float = 0.0
    ocr_text: str = ""
    translated_text: Optional[str] = None
    status: str = "pending"


class PaginatedPagesResponse(BaseModel):
    job_id: str
    pages: list[dict]
    total: int
    page: int
    limit: int
    has_more: bool


class HealthComponent(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    writable: Optional[bool] = None
    model_loaded: Optional[bool] = None


class DetailedHealthResponse(BaseModel):
    status: str
    components: dict[str, HealthComponent]


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
