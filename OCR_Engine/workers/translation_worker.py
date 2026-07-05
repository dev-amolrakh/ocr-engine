import structlog

from workers.base_worker import BaseWorker
from mq.streams import STREAM_LANGDETECT_QUEUE, STREAM_TRANSLATION_QUEUE
from mq.producer import push_to_stream
from ml.translation_client import translate_text
from db.mongo import get_db

log = structlog.get_logger()


class TranslationWorker(BaseWorker):
    consumer_stream = STREAM_LANGDETECT_QUEUE

    async def process_message(self, msg: dict):
        job_id = msg["job_id"]
        page = int(msg["page"])
        ocr_text = msg.get("ocr_text", "")
        language = msg.get("language", "en")

        # Translate to English (no-op if already English)
        translated_text = await translate_text(ocr_text, src_lang=language)

        # Update page document
        db = get_db()
        await db.ocr_pages.update_one(
            {"job_id": job_id, "page": page},
            {"$set": {
                "translated_text": translated_text,
                "status": "translated",
            }},
            upsert=True
        )

        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "translation"}}
        )

        # Push to extraction stage
        await push_to_stream(STREAM_TRANSLATION_QUEUE, {
            "job_id": job_id,
            "page": str(page),
            "translated_text": translated_text,
            "language": language,
            "retry_count": "0",
        })

        log.info("translation_complete", job_id=job_id, page=page,
                 language=language, translated=(language != "en"))
