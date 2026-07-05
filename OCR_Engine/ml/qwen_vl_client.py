import base64
import httpx
from config import settings
import structlog

log = structlog.get_logger()

HANDWRITING_PROMPT = """You are an expert OCR system specializing in handwritten and degraded document text.

Carefully read ALL text visible in this document image. Include:
- All handwritten text (even partially legible)
- Printed text
- Stamps, seals, signatures descriptions (describe as [STAMP: text] or [SIGNATURE])
- Numbers, dates, amounts
- Text in any Indian language (write in the original script)
- Mixed language content

Output ONLY the extracted text, preserving the original line structure.
Do not add explanations, comments, or formatting markers.
If a word is partially illegible, output your best guess with [?] after it."""

PRINTED_FALLBACK_PROMPT = """Extract all text from this document image.
Output only the extracted text preserving line order.
Include all languages, numbers, and special characters exactly as written."""


async def qwen_vl_ocr(image_path: str, is_handwritten: bool = False) -> dict:
    """
    Call Qwen-VL via Ollama for OCR.
    Used when handwriting detected or PaddleOCR confidence < threshold.
    """
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    prompt = HANDWRITING_PROMPT if is_handwritten else PRINTED_FALLBACK_PROMPT

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.QWEN_VL_MODEL,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_ctx": 4096,
                    "num_predict": 2048,
                }
            }
        )
        response.raise_for_status()

    data = response.json()
    extracted_text = data.get("response", "").strip()

    return {
        "text": extracted_text,
        "confidence": 1.0,
        "source": "qwen_vl",
        "model": settings.QWEN_VL_MODEL,
    }


async def qwen_vl_batch(items: list[dict]) -> list[dict]:
    """
    Process a batch of images with Qwen-VL.
    items: [{"image_path": str, "is_handwritten": bool, "job_id": str, "page": int}]
    """
    import asyncio
    tasks = [
        qwen_vl_ocr(item["image_path"], item.get("is_handwritten", False))
        for item in items
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for item, result in zip(items, results):
        if isinstance(result, Exception):
            log.error("qwen_vl_failed", job_id=item.get("job_id"),
                      page=item.get("page"), error=str(result))
            output.append({**item, "text": "", "confidence": 0.0, "error": str(result)})
        else:
            output.append({**item, **result})
    return output
