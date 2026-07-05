import asyncio
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF
import structlog

from workers.base_worker import BaseWorker
from mq.streams import STREAM_DOCUMENT_QUEUE, STREAM_RENDER_QUEUE
from mq.producer import push_to_stream
from db.mongo import get_db
from config import settings

log = structlog.get_logger()


class RendererWorker(BaseWorker):
    consumer_stream = STREAM_DOCUMENT_QUEUE

    async def process_message(self, msg: dict):
        job_id = msg["job_id"]
        file_path = msg["file_path"]
        mime_type = msg.get("mime_type", "application/pdf")

        db = get_db()
        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "rendering", "started_at": datetime.utcnow()}}
        )

        if mime_type.startswith("image/"):
            await push_to_stream(STREAM_RENDER_QUEUE, {
                "job_id": job_id,
                "page": "1",
                "image_path": file_path,
                "retry_count": "0",
            })
            log.info("render_image_passthrough", job_id=job_id)
            return

        # PDF rendering (CPU-bound, run in executor)
        loop = asyncio.get_event_loop()
        rendered_pages = await loop.run_in_executor(
            None, self._render_pdf, file_path
        )

        # Push each rendered page to the next queue (async)
        for page_num, image_path in rendered_pages:
            await push_to_stream(STREAM_RENDER_QUEUE, {
                "job_id": job_id,
                "page": str(page_num),
                "image_path": image_path,
                "retry_count": "0",
            })

        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {"total_pages": len(rendered_pages)}}
        )

        log.info("render_complete", job_id=job_id, pages=len(rendered_pages))

    def _render_pdf(self, file_path: str) -> list[tuple[int, str]]:
        """Render PDF pages to PNG images. Returns [(page_num, image_path)]."""
        doc = fitz.open(file_path)
        page_count = len(doc)

        output_dir = Path(file_path).parent / "pages"
        output_dir.mkdir(exist_ok=True, parents=True)

        rendered = []
        zoom = settings.PREPROCESS_TARGET_DPI / 72
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(page_count):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)

            image_path = output_dir / f"page_{page_num + 1:04d}.png"
            pix.save(str(image_path))
            rendered.append((page_num + 1, str(image_path)))

        doc.close()
        return rendered
