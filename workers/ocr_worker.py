import structlog

from workers.base_worker import BaseWorker
from mq.streams import STREAM_PREPROCESS_QUEUE, STREAM_OCR_QUEUE
from mq.producer import push_to_stream
from ml.ocr_router import route_ocr
from db.mongo import get_db
from config import settings

log = structlog.get_logger()


class OCRWorker(BaseWorker):
    consumer_stream = STREAM_PREPROCESS_QUEUE

    async def process_message(self, msg: dict):
        job_id = msg.get("job_id")
        page = int(msg.get("page", 0))
        image_path = msg.get("image_path")
        if not image_path:
            raise ValueError(f"Missing image_path in message for job {job_id}, skipping")
        preprocessed_path = msg.get("preprocessed_path", image_path)
        lang = msg.get("lang", "en")

        # Run OCR via hybrid router (PaddleOCR -> Qwen-VL fallback)
        ocr_result = await route_ocr(
            image_path=image_path,
            preprocessed_path=preprocessed_path,
            lang=lang,
            job_id=job_id,
            page=page,
        )

        # Update MongoDB page document
        db = get_db()
        await db.ocr_pages.update_one(
            {"job_id": job_id, "page": page},
            {"$set": {
                "ocr_text": ocr_result["text"],
                "ocr_source": ocr_result["ocr_source"],
                "ocr_confidence": ocr_result.get("confidence", 0.0),
                "is_handwritten": ocr_result.get("is_handwritten", False),
                "status": "ocr_complete",
            }},
            upsert=True
        )

        # Update job-level OCR stats
        source_field = "paddle_pages" if ocr_result["ocr_source"] == "paddle" else "qwen_vl_pages"
        inc_fields = {source_field: 1}
        if ocr_result.get("is_handwritten"):
            inc_fields["handwritten_pages"] = 1
        await db.jobs.update_one(
            {"job_id": job_id},
            {"$inc": inc_fields, "$set": {"status": "ocr"}}
        )

        # Push to next stage (language detection)
        await push_to_stream(STREAM_OCR_QUEUE, {
            "job_id": job_id,
            "page": str(page),
            "lang": lang,
            "ocr_text": ocr_result["text"],
            "ocr_source": ocr_result["ocr_source"],
            "retry_count": "0",
        })

        log.info("ocr_complete", job_id=job_id, page=page,
                 source=ocr_result["ocr_source"],
                 confidence=round(ocr_result.get("confidence", 0), 3))
