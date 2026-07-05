import asyncio
import structlog
from pathlib import Path

from config import settings

log = structlog.get_logger()

_translator = None

# IndicTrans2 language code mapping (BCP-47 → IndicTrans2 format)
INDIC_LANG_MAP = {
    "hi": "hin_Deva",
    "mr": "mar_Deva",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "kn": "kan_Knda",
    "bn": "ben_Beng",
}

TARGET_LANG = "eng_Latn"


def _load_translator():
    """Load IndicTrans2 model (singleton). Heavy — loaded once on first use."""
    global _translator
    if _translator is not None:
        return _translator

    model_path = settings.INDICTRANS2_MODEL_PATH

    if not Path(model_path).exists():
        log.warning("indictrans2_not_found", path=model_path)
        return None

    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    log.info("loading_indictrans2", path=model_path)

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_path,
        trust_remote_code=True,
    )

    # Try loading IndicProcessor for proper preprocessing
    ip = None
    try:
        from IndicTransToolkit import IndicProcessor
        ip = IndicProcessor(inference=True)
        log.info("indic_processor_loaded")
    except ImportError:
        log.warning("IndicTransToolkit not installed, using basic tokenization")

    _translator = {"model": model, "tokenizer": tokenizer, "processor": ip}
    log.info("indictrans2_loaded")
    return _translator


def _translate_sync(text: str, src_lang: str) -> str:
    """Synchronous translation call. Run via executor."""
    if not text or src_lang == "en":
        return text

    src_code = INDIC_LANG_MAP.get(src_lang)
    if not src_code:
        log.warning("unsupported_translation_lang", lang=src_lang)
        return text

    translator = _load_translator()
    if translator is None:
        log.warning("indictrans2_unavailable, returning original text")
        return text

    tokenizer = translator["tokenizer"]
    model = translator["model"]
    processor = translator["processor"]

    # Preprocess with IndicProcessor if available
    if processor:
        batch = processor.preprocess_batch(
            [text], src_lang=src_code, tgt_lang=TARGET_LANG
        )
        input_text = batch[0]
    else:
        input_text = text

    inputs = tokenizer(
        input_text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )

    outputs = model.generate(
        **inputs,
        max_length=512,
        num_beams=5,
        num_return_sequences=1,
        early_stopping=True,
    )

    raw_translation = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Postprocess with IndicProcessor if available
    if processor:
        result = processor.postprocess_batch(
            [raw_translation], lang=TARGET_LANG
        )
        return result[0]

    return raw_translation


async def translate_text(text: str, src_lang: str) -> str:
    """Async wrapper for translation. Non-blocking via executor."""
    if not text or src_lang == "en":
        return text

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _translate_sync, text, src_lang)
    return result


async def translate_batch(items: list[dict]) -> list[dict]:
    """
    Translate a batch of texts.
    items: [{"text": str, "src_lang": str, "job_id": str, "page": int}]
    """
    tasks = [translate_text(item["text"], item["src_lang"]) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for item, result in zip(items, results):
        if isinstance(result, Exception):
            log.error("translation_failed", job_id=item.get("job_id"),
                      page=item.get("page"), error=str(result))
            output.append({**item, "translated_text": item["text"], "error": str(result)})
        else:
            output.append({**item, "translated_text": result})
    return output
