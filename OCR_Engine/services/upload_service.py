import fitz  # PyMuPDF
from datetime import datetime
import structlog

from db.mongo import get_db
from mq.producer import push_to_stream
from mq.streams import STREAM_DOCUMENT_QUEUE
from services.file_service import save_upload
from utils.id_generator import generate_job_id
from models.enums import JobStatus

log = structlog.get_logger()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
}


async def process_upload(file_content: bytes, filename: str,
                         mime_type: str, metadata: dict | None = None) -> dict:
    """
    Handle a single file upload:
    1. Generate job_id
    2. Save to NFS
    3. Count pages
    4. Insert job to MongoDB
    5. Push to document queue
    6. Return job info
    """
    job_id = generate_job_id()

    # Validate mime type
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported file type: {mime_type}. Allowed: {ALLOWED_MIME_TYPES}")

    # Save file
    file_path = await save_upload(file_content, filename, job_id)

    # Count pages
    total_pages = 1
    if mime_type == "application/pdf":
        total_pages = _count_pdf_pages(file_path)

    # Insert job document
    job_doc = {
        "job_id": job_id,
        "file_name": filename,
        "file_path": file_path,
        "file_size_bytes": len(file_content),
        "mime_type": mime_type,
        "total_pages": total_pages,
        "processed_pages": 0,
        "failed_pages": 0,
        "handwritten_pages": 0,
        "paddle_pages": 0,
        "qwen_vl_pages": 0,
        "status": JobStatus.QUEUED,
        "doc_type": "unknown",
        "uploaded_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None,
        "error": None,
        "metadata": metadata or {},
    }

    db = get_db()
    await db.jobs.insert_one(job_doc)

    # Push to processing queue
    await push_to_stream(STREAM_DOCUMENT_QUEUE, {
        "job_id": job_id,
        "file_path": file_path,
        "mime_type": mime_type,
        "total_pages": str(total_pages),
        "retry_count": "0",
    })

    log.info("upload_processed", job_id=job_id, filename=filename,
             pages=total_pages, size=len(file_content))

    return {
        "job_id": job_id,
        "status": "queued",
        "total_pages": total_pages,
        "poll_url": f"/api/v1/jobs/{job_id}",
    }


def _count_pdf_pages(file_path: str) -> int:
    """Count pages in a PDF file. Also validates the PDF is readable."""
    try:
        doc = fitz.open(file_path)
        count = len(doc)
        doc.close()
        return count
    except Exception as e:
        raise ValueError(f"Invalid or corrupted PDF: {e}")
