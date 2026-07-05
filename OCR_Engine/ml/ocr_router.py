from ml.paddle_ocr_client import paddle_ocr
from ml.qwen_vl_client import qwen_vl_ocr
from ml.image_processor import detect_handwriting
from config import settings
import structlog

log = structlog.get_logger()

# Phrases that indicate the VL model is refusing/confused (not actual OCR)
VL_REFUSAL_PHRASES = [
    "sorry", "i cannot", "i can't", "no image", "no document",
    "not attached", "please provide", "upload", "i'm unable",
    "as an ai", "i don't see",
]


def _is_valid_ocr_text(text: str) -> bool:
    """Check if VL output is actual OCR text vs a refusal/confusion message."""
    if not text or len(text) < 10:
        return False
    text_lower = text.lower()
    for phrase in VL_REFUSAL_PHRASES:
        if phrase in text_lower:
            return False
    return True


async def route_ocr(image_path: str, preprocessed_path: str,
                    lang: str = "en", job_id: str = "", page: int = 0) -> dict:
    """
    Hybrid OCR router — PaddleOCR first, always returns usable text.

    Logic:
      1. Run PaddleOCR (English)
      2. If low confidence + lang is "en" → retry with Hindi model
      3. If best confidence >= threshold → accept PaddleOCR
      4. If below threshold → try Qwen-VL (only if vision model available)
      5. Validate VL result (reject refusal messages)
      6. Fallback: always use PaddleOCR result (even at low confidence)
    """
    log_ctx = log.bind(job_id=job_id, page=page, lang=lang)

    is_handwritten = detect_handwriting(preprocessed_path)
    log_ctx.debug("handwriting_detection", is_handwritten=is_handwritten)

    # Step 1: Run PaddleOCR with specified language
    paddle_result = await paddle_ocr(preprocessed_path, lang=lang)
    confidence = paddle_result.get("confidence", 0.0)
    log_ctx.debug("paddle_result", confidence=round(confidence, 3),
                  text_len=len(paddle_result.get("text", "")))

    # Step 2: If confidence is low and lang was "en", retry with Hindi
    if confidence < settings.PADDLE_CONFIDENCE_THRESHOLD and lang == "en":
        hi_result = await paddle_ocr(preprocessed_path, lang="hi")
        hi_confidence = hi_result.get("confidence", 0.0)
        log_ctx.debug("paddle_hindi_retry", confidence=round(hi_confidence, 3),
                      text_len=len(hi_result.get("text", "")))
        if hi_confidence > confidence:
            paddle_result = hi_result
            confidence = hi_confidence
            log_ctx.info("paddle_hindi_better",
                         en_conf=round(confidence, 3),
                         hi_conf=round(hi_confidence, 3))

    # Step 3: Accept PaddleOCR if confidence is good enough
    # Use slightly lower threshold (0.70) for non-English since Hindi/Devanagari
    # models typically produce lower raw confidence scores
    effective_threshold = settings.PADDLE_CONFIDENCE_THRESHOLD
    if lang != "en" or confidence > 0.65:
        effective_threshold = min(effective_threshold, 0.70)

    if confidence >= effective_threshold:
        log_ctx.info("ocr_route", path="paddle_accepted", confidence=round(confidence, 3))
        return {**paddle_result, "ocr_source": "paddle", "is_handwritten": is_handwritten}

    # Step 4: Try Qwen-VL only if a real vision model is configured
    log_ctx.info("ocr_route", path="qwen_vl_attempt",
                 paddle_confidence=round(confidence, 3))

    try:
        vl_result = await qwen_vl_ocr(preprocessed_path, is_handwritten=is_handwritten)
        vl_text = vl_result.get("text", "")

        # Step 5: Validate VL result — reject refusals
        if _is_valid_ocr_text(vl_text):
            log_ctx.info("ocr_route", path="qwen_vl_accepted", vl_text_len=len(vl_text))
            return {
                **vl_result,
                "ocr_source": "qwen_vl",
                "is_handwritten": is_handwritten,
                "paddle_fallback_confidence": confidence,
            }
        else:
            log_ctx.warning("qwen_vl_rejected", reason="refusal_or_garbage",
                            vl_text_preview=vl_text[:100])

    except Exception as e:
        log_ctx.warning("qwen_vl_failed", error=str(e)[:150])

    # Step 6: Use PaddleOCR result (always available, even at lower confidence)
    log_ctx.info("ocr_route", path="paddle_final_fallback",
                 confidence=round(confidence, 3))
    return {
        **paddle_result,
        "ocr_source": "paddle",
        "is_handwritten": is_handwritten,
    }
