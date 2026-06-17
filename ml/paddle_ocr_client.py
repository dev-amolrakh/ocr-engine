import asyncio
from functools import lru_cache
from paddleocr import PaddleOCR
from config import settings
import structlog

log = structlog.get_logger()

LANG_MAP = {
    "hi": "hi",
    "mr": "hi",      # Marathi uses Devanagari — same as Hindi model
    "ta": "ta",
    "te": "te",
    "kn": "ka",
    "bn": "en",      # Bengali fallback to English; Qwen-VL handles rest
    "en": "en",
    "mixed": "en",
    "unknown": "en",
}


@lru_cache(maxsize=8)
def _get_paddle_model(lang: str) -> PaddleOCR:
    """Cache PaddleOCR models by language — only loaded once per process."""
    log.info("loading_paddle_model", lang=lang)
    return PaddleOCR(
        use_angle_cls=True,
        lang=lang,
        use_gpu=settings.PADDLE_USE_GPU,
        det_db_thresh=settings.PADDLE_DET_DB_THRESH,
        det_db_box_thresh=settings.PADDLE_DET_DB_BOX_THRESH,
        rec_batch_num=8,
        show_log=False,
    )


def _run_paddle_sync(image_path: str, lang: str) -> dict:
    """Synchronous OCR call. Must be run via executor in async context."""
    paddle_lang = LANG_MAP.get(lang, "en")
    model = _get_paddle_model(paddle_lang)

    result = model.ocr(image_path, cls=True)

    if not result or not result[0]:
        return {"text": "", "confidence": 0.0, "boxes": []}

    lines = []
    confidences = []

    for line in result[0]:
        bbox, (text, conf) = line
        lines.append(text)
        confidences.append(conf)

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    full_text = "\n".join(lines)

    return {
        "text": full_text,
        "confidence": avg_confidence,
        "boxes": result[0],
        "line_count": len(lines),
    }


async def paddle_ocr(image_path: str, lang: str = "en") -> dict:
    """Async wrapper for PaddleOCR. Non-blocking via executor."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_paddle_sync, image_path, lang)
    return result


async def paddle_ocr_batch(items: list[dict]) -> list[dict]:
    """
    Process a batch of images concurrently.
    items: [{"image_path": str, "lang": str, "job_id": str, "page": int}]
    """
    tasks = [paddle_ocr(item["image_path"], item.get("lang", "en")) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for item, result in zip(items, results):
        if isinstance(result, Exception):
            output.append({**item, "text": "", "confidence": 0.0, "error": str(result)})
        else:
            output.append({**item, **result})
    return output
