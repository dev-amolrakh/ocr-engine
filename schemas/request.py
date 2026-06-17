from pydantic import BaseModel, Field


class BulkStatusRequest(BaseModel):
    job_ids: list[str] = Field(..., max_length=100)


class UploadMetadata(BaseModel):
    doc_type: str | None = None
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
