import asyncio
from pathlib import Path
import structlog

from workers.base_worker import BaseWorker
from mq.streams import STREAM_RENDER_QUEUE, STREAM_PREPROCESS_QUEUE
from mq.producer import push_to_stream
from ml.image_processor import preprocess_for_ocr
from config import settings

log = structlog.get_logger()


class PreprocessorWorker(BaseWorker):
    consumer_stream = STREAM_RENDER_QUEUE

    async def process_message(self, msg: dict):
        job_id = msg.get("job_id")
        page = int(msg.get("page", 0))
        image_path = msg.get("image_path")
        if not image_path:
            raise ValueError(f"Missing image_path in message for job {job_id}, skipping")

        image_p = Path(image_path)
        clean_dir = image_p.parent / "clean"
        clean_dir.mkdir(exist_ok=True, parents=True)
        preprocessed_path = str(clean_dir / image_p.name)

        # CPU-bound preprocessing — run in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            preprocess_for_ocr,
            image_path,
            preprocessed_path,
            settings.PREPROCESS_HANDWRITING_MODE,
        )

        # Forward to OCR stage
        await push_to_stream(STREAM_PREPROCESS_QUEUE, {
            "job_id": job_id,
            "page": str(page),
            "image_path": image_path,
            "preprocessed_path": preprocessed_path,
            "retry_count": "0",
        })

        log.info("preprocess_complete", job_id=job_id, page=page)
