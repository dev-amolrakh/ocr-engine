import asyncio
from pathlib import Path
import structlog

from config import settings

log = structlog.get_logger()

_model = None


def _load_model():
    """Load fastText language identification model (singleton)."""
    global _model
    if _model is None:
        import fasttext
        model_path = settings.FASTTEXT_MODEL_PATH
        if not Path(model_path).exists():
            raise FileNotFoundError(f"fastText model not found: {model_path}")
        _model = fasttext.load_model(model_path)
        log.info("fasttext_model_loaded", path=model_path)
    return _model


def _detect_sync(text: str) -> dict:
    """Synchronous language detection. Run via executor."""
    if not text or len(text.strip()) < 5:
        return {"language": "unknown", "confidence": 0.0}

    model = _load_model()
    # fastText returns labels like '__label__hi'
    predictions = model.predict(text.replace("\n", " "), k=3)
    labels, scores = predictions

    top_lang = labels[0].replace("__label__", "")
    top_score = float(scores[0])

    supported = {"hi", "mr", "ta", "te", "kn", "bn", "en"}
    if top_lang not in supported:
        # Check if second prediction is a supported language
        if len(labels) > 1:
            second_lang = labels[1].replace("__label__", "")
            if second_lang in supported:
                return {"language": second_lang, "confidence": float(scores[1])}
        return {"language": "unknown", "confidence": top_score}

    return {"language": top_lang, "confidence": top_score}


async def detect_language(text: str) -> dict:
    """Async wrapper for language detection."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _detect_sync, text)
    return result


async def detect_language_batch(texts: list[str]) -> list[dict]:
    """Detect language for a batch of texts."""
    tasks = [detect_language(text) for text in texts]
    return await asyncio.gather(*tasks)
