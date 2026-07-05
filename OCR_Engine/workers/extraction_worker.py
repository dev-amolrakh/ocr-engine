import structlog
from datetime import datetime

from workers.base_worker import BaseWorker
from mq.streams import STREAM_TRANSLATION_QUEUE, STREAM_EXTRACTION_QUEUE
from mq.producer import push_to_stream
from ml.extraction_client import extract_structured_data, classify_document
from db.mongo import get_db

log = structlog.get_logger()


class ExtractionWorker(BaseWorker):
    consumer_stream = STREAM_TRANSLATION_QUEUE

    async def process_message(self, msg: dict):
        job_id = msg.get("job_id")
        page = int(msg.get("page", 0))
        translated_text = msg.get("translated_text", "")

        db = get_db()

        # Get job to check if doc_type already classified
        job = await db.jobs.find_one({"job_id": job_id})
        doc_type = job.get("doc_type", "unknown") if job else "unknown"

        # Classify document type if unknown
        if doc_type == "unknown":
            # Use all OCR text accumulated so far for better classification
            all_text = translated_text
            if page > 1:
                pages_cursor = db.ocr_pages.find(
                    {"job_id": job_id}, {"ocr_text": 1, "_id": 0}
                )
                pages_data = await pages_cursor.to_list(length=100)
                all_text = "\n".join(p.get("ocr_text", "") for p in pages_data)

            doc_type = await classify_document(all_text)
            await db.jobs.update_one(
                {"job_id": job_id},
                {"$set": {"doc_type": doc_type, "status": "extraction"}}
            )
            log.info("document_classified", job_id=job_id, doc_type=doc_type)

        # Extract structured data (smart rules first, LLM fallback)
        extraction_result = await extract_structured_data(translated_text, doc_type)

        # Store extraction result
        await db.extracted_data.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "doc_type": doc_type,
                    "extracted_data": extraction_result["extracted_data"],
                    "raw_ocr_text": extraction_result.get("raw_ocr_text", translated_text),
                    "extraction_method": extraction_result.get("extraction_method", "unknown"),
                    "extracted_at": datetime.utcnow(),
                },
                "$push": {
                    "page_extractions": {
                        "page": page,
                        "data": extraction_result["extracted_data"],
                    }
                }
            },
            upsert=True
        )

        # Update page status
        await db.ocr_pages.update_one(
            {"job_id": job_id, "page": page},
            {"$set": {"status": "extracted"}},
            upsert=True
        )

        # Push to validation stage
        await push_to_stream(STREAM_EXTRACTION_QUEUE, {
            "job_id": job_id,
            "page": str(page),
            "doc_type": doc_type,
            "retry_count": "0",
        })

        log.info("extraction_complete", job_id=job_id, page=page,
                 doc_type=doc_type,
                 method=extraction_result.get("extraction_method"))
