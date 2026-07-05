from db.mongo import get_db
import structlog

log = structlog.get_logger()


async def get_job_results(job_id: str) -> dict | None:
    """Assemble final results for a completed job."""
    db = get_db()

    job = await db.jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        return None

    extraction = await db.extracted_data.find_one({"job_id": job_id}, {"_id": 0})

    # Get language stats
    pages_cursor = db.ocr_pages.find(
        {"job_id": job_id},
        {"language": 1, "_id": 0}
    )
    pages = await pages_cursor.to_list(length=1000)
    languages = list(set(p.get("language") for p in pages if p.get("language")))

    translated_count = await db.ocr_pages.count_documents(
        {"job_id": job_id, "translated_text": {"$ne": None}}
    )

    # Get raw OCR text from all pages
    ocr_pages_cursor = db.ocr_pages.find(
        {"job_id": job_id},
        {"ocr_text": 1, "page": 1, "_id": 0}
    ).sort("page", 1)
    ocr_pages_data = await ocr_pages_cursor.to_list(length=1000)
    raw_ocr_text = "\n".join(p.get("ocr_text", "") for p in ocr_pages_data)

    extracted_data = extraction.get("extracted_data", {}) if extraction else {}
    # Remove internal flags from response
    extracted_data.pop("_extraction_skipped", None)
    extracted_data.pop("_reason", None)

    result = {
        "job_id": job_id,
        "status": job["status"],
        "doc_type": job.get("doc_type", "unknown"),
        "extracted_data": extracted_data,
        "raw_ocr_text": raw_ocr_text,
        "confidence": extraction.get("confidence", 0.0) if extraction else 0.0,
        "validated": extraction.get("validated", False) if extraction else False,
        "validation_errors": extraction.get("validation_errors", []) if extraction else [],
        "extraction_method": extraction.get("extraction_method", "unknown") if extraction else "unknown",
        "ocr_summary": {
            "total_pages": job.get("total_pages", 0),
            "languages_detected": languages,
            "pages_translated": translated_count,
            "paddle_pages": job.get("paddle_pages", 0),
            "qwen_vl_pages": job.get("qwen_vl_pages", 0),
            "handwritten_pages": job.get("handwritten_pages", 0),
        },
    }

    return result


async def get_page_result(job_id: str, page_num: int) -> dict | None:
    """Get OCR result for a single page."""
    db = get_db()
    page = await db.ocr_pages.find_one(
        {"job_id": job_id, "page": page_num},
        {"_id": 0}
    )
    return page


async def get_all_pages(job_id: str, page: int = 1, limit: int = 20) -> dict:
    """Get all pages for a job with pagination."""
    db = get_db()

    skip = (page - 1) * limit
    total = await db.ocr_pages.count_documents({"job_id": job_id})

    cursor = db.ocr_pages.find(
        {"job_id": job_id},
        {"_id": 0}
    ).sort("page", 1).skip(skip).limit(limit)

    pages = await cursor.to_list(length=limit)

    return {
        "job_id": job_id,
        "pages": pages,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (skip + limit) < total,
    }
