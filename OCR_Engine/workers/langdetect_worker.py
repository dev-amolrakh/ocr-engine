import structlog

from workers.base_worker import BaseWorker
from mq.streams import STREAM_OCR_QUEUE, STREAM_LANGDETECT_QUEUE
from mq.producer import push_to_stream
from ml.langdetect_client import detect_language
from db.mongo import get_db

log = structlog.get_logger()


class LangDetectWorker(BaseWorker):
    consumer_stream = STREAM_OCR_QUEUE

    async def process_message(self, msg: dict):
        job_id = msg["job_id"]
        page = int(msg["page"])
        ocr_text = msg.get("ocr_text", "")

        # Detect language
        lang_result = await detect_language(ocr_text)
        detected_lang = lang_result["language"]
        lang_confidence = lang_result["confidence"]

        # Update page document with detected language
        db = get_db()
        await db.ocr_pages.update_one(
            {"job_id": job_id, "page": page},
            {"$set": {
                "language": detected_lang,
                "lang_confidence": lang_confidence,
                "status": "lang_detected",
            }},
            upsert=True
        )

        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "lang_detection"}}
        )

        # Push to translation stage
        await push_to_stream(STREAM_LANGDETECT_QUEUE, {
            "job_id": job_id,
            "page": str(page),
            "ocr_text": ocr_text,
            "language": detected_lang,
            "retry_count": "0",
        })

        log.info("langdetect_complete", job_id=job_id, page=page,
                 language=detected_lang, confidence=round(lang_confidence, 3))
