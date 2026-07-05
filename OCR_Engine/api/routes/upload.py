import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional

from services.upload_service import process_upload, ALLOWED_MIME_TYPES
from schemas.response import UploadResponse, BulkUploadResponse
from utils.metrics import jobs_uploaded_total, upload_duration_seconds
from config import settings
import structlog
import time

log = structlog.get_logger()

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_file(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
):
    """Upload a single PDF or image for OCR processing."""
    start = time.perf_counter()

    # Validate file size
    content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Validate MIME type
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {mime_type}. Allowed: {list(ALLOWED_MIME_TYPES)}"
        )

    # Parse metadata
    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    result = await process_upload(
        file_content=content,
        filename=file.filename or "document",
        mime_type=mime_type,
        metadata=meta,
    )

    jobs_uploaded_total.labels(mime_type=mime_type).inc()
    upload_duration_seconds.observe(time.perf_counter() - start)

    return UploadResponse(**result)


@router.post("/upload/bulk", response_model=BulkUploadResponse, status_code=202)
async def upload_bulk(
    files: list[UploadFile] = File(...),
):
    """Upload up to 50 files for batch OCR processing."""
    if len(files) > settings.MAX_BULK_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Max: {settings.MAX_BULK_FILES}"
        )

    results = []
    for file in files:
        content = await file.read()

        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_size:
            continue  # Skip oversized files

        mime_type = file.content_type or "application/octet-stream"
        if mime_type not in ALLOWED_MIME_TYPES:
            continue  # Skip unsupported types

        result = await process_upload(
            file_content=content,
            filename=file.filename or "document",
            mime_type=mime_type,
        )
        results.append(UploadResponse(**result))
        jobs_uploaded_total.labels(mime_type=mime_type).inc()

    return BulkUploadResponse(jobs=results, total_files=len(results))
