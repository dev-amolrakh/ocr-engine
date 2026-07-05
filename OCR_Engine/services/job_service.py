from db.mongo import get_db
from mq.producer import push_to_stream
from mq.streams import STREAM_DOCUMENT_QUEUE
from services.file_service import archive_file
import structlog

log = structlog.get_logger()


async def get_job_status(job_id: str) -> dict | None:
    """Get full job status with OCR stats."""
    db = get_db()
    job = await db.jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        return None

    total_pages = job.get("total_pages", 0)
    processed = job.get("processed_pages", 0)
    progress_pct = round((processed / total_pages * 100), 1) if total_pages > 0 else 0.0

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "total_pages": total_pages,
        "processed_pages": processed,
        "failed_pages": job.get("failed_pages", 0),
        "progress_pct": progress_pct,
        "doc_type": job.get("doc_type", "unknown"),
        "ocr_stats": {
            "paddle_pages": job.get("paddle_pages", 0),
            "qwen_vl_pages": job.get("qwen_vl_pages", 0),
            "handwritten_pages": job.get("handwritten_pages", 0),
        },
        "uploaded_at": job.get("uploaded_at"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "error": job.get("error"),
    }


async def get_bulk_status(job_ids: list[str]) -> list[dict]:
    """Get status for multiple jobs in one query."""
    db = get_db()
    cursor = db.jobs.find(
        {"job_id": {"$in": job_ids}},
        {"_id": 0}
    )
    jobs = await cursor.to_list(length=len(job_ids))

    results = []
    for job in jobs:
        total = job.get("total_pages", 0)
        processed = job.get("processed_pages", 0)
        results.append({
            "job_id": job["job_id"],
            "status": job["status"],
            "total_pages": total,
            "processed_pages": processed,
            "progress_pct": round((processed / total * 100), 1) if total > 0 else 0.0,
            "doc_type": job.get("doc_type", "unknown"),
        })

    return results


async def retry_job(job_id: str) -> dict | None:
    """Reset a failed job and re-queue it."""
    db = get_db()
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        return None

    # Delete existing page docs
    await db.ocr_pages.delete_many({"job_id": job_id})
    await db.extracted_data.delete_many({"job_id": job_id})

    # Reset job
    await db.jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": "queued",
            "processed_pages": 0,
            "failed_pages": 0,
            "handwritten_pages": 0,
            "paddle_pages": 0,
            "qwen_vl_pages": 0,
            "started_at": None,
            "completed_at": None,
            "error": None,
        }}
    )

    # Re-queue
    await push_to_stream(STREAM_DOCUMENT_QUEUE, {
        "job_id": job_id,
        "file_path": job["file_path"],
        "mime_type": job["mime_type"],
        "total_pages": str(job["total_pages"]),
        "retry_count": "0",
    })

    log.info("job_retried", job_id=job_id)
    return {"job_id": job_id, "status": "queued", "message": "Job re-queued"}


async def delete_job(job_id: str) -> bool:
    """Delete a job and archive its file."""
    db = get_db()
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        return False

    # Archive the file
    await archive_file(job.get("file_path", ""), job_id)

    # Delete all related documents
    await db.jobs.delete_one({"job_id": job_id})
    await db.ocr_pages.delete_many({"job_id": job_id})
    await db.extracted_data.delete_many({"job_id": job_id})
    await db.failed_jobs.delete_many({"job_id": job_id})

    log.info("job_deleted", job_id=job_id)
    return True
