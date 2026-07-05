"""
Hybrid extraction: Smart rules first, LLM fallback for unknown documents.
"""
import json
import re
import httpx
from pathlib import Path
from config import settings
from ml.smart_classifier import classify_document_by_keywords
from ml.smart_extractor import smart_extract
import structlog

log = structlog.get_logger()

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(doc_type: str) -> str:
    """Load the extraction prompt template for a given document type."""
    prompt_file = PROMPTS_DIR / f"{doc_type}.txt"
    if not prompt_file.exists():
        prompt_file = PROMPTS_DIR / "generic.txt"
    return prompt_file.read_text(encoding="utf-8")


async def extract_structured_data(text: str, doc_type: str) -> dict:
    """
    Hybrid extraction pipeline:
    1. Try smart regex-based extraction (fast, accurate for known docs)
    2. Fall back to LLM extraction for unknown/complex documents
    3. Always include raw_ocr_text in output
    """
    # Step 1: Smart extraction for known document types
    smart_result = smart_extract(text, doc_type)

    if smart_result and len(smart_result) >= 2:
        # Smart extraction worked — high confidence
        log.info("extraction_method", method="smart_rules", doc_type=doc_type,
                 fields=len(smart_result))
        return {
            "extracted_data": smart_result,
            "raw_ocr_text": text,
            "doc_type": doc_type,
            "extraction_method": "smart_rules",
            "model": "regex_patterns",
        }

    # Step 2: Try LLM extraction as fallback
    llm_result = await _llm_extract(text, doc_type)

    if llm_result:
        # Merge smart + LLM results (smart takes priority for overlap)
        merged = {**(llm_result or {}), **(smart_result or {})}
        return {
            "extracted_data": merged,
            "raw_ocr_text": text,
            "doc_type": doc_type,
            "extraction_method": "hybrid" if smart_result else "llm",
            "model": settings.EXTRACTION_MODEL,
        }

    # Step 3: If everything fails, return what we have
    return {
        "extracted_data": smart_result or {"_note": "extraction_incomplete"},
        "raw_ocr_text": text,
        "doc_type": doc_type,
        "extraction_method": "smart_rules_only" if smart_result else "none",
        "model": "regex_patterns",
    }


async def _llm_extract(text: str, doc_type: str) -> dict | None:
    """Attempt LLM-based extraction. Returns None if LLM is unavailable."""
    prompt_template = _load_prompt(doc_type)
    full_prompt = prompt_template.replace("{text}", text)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.EXTRACTION_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_ctx": 2048,
                        "num_predict": 1024,
                    }
                }
            )
            response.raise_for_status()

        data = response.json()
        raw_response = data.get("response", "").strip()

        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
        return None

    except Exception as e:
        log.warning("llm_extraction_unavailable", error=str(e)[:150])
        return None


async def classify_document(text: str) -> str:
    """
    Hybrid document classification:
    1. Keyword-based classification (fast, accurate)
    2. LLM fallback only if keywords don't match
    """
    # Step 1: Smart keyword classification (always accurate)
    doc_type = classify_document_by_keywords(text)
    if doc_type != "unknown":
        log.info("classification_method", method="keywords", doc_type=doc_type)
        return doc_type

    # Step 2: LLM fallback for unknown documents
    try:
        prompt_template = _load_prompt("classify")
        full_prompt = prompt_template.replace("{text}", text[:2000])

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.EXTRACTION_MODEL,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_ctx": 2048,
                        "num_predict": 50,
                    }
                }
            )
            response.raise_for_status()

        data = response.json()
        doc_type = data.get("response", "").strip().lower()

        valid_types = {
            "invoice", "aadhaar", "fra_form", "land_claim",
            "certificate", "pan_card", "ration_card", "birth_certificate",
        }
        if doc_type in valid_types:
            log.info("classification_method", method="llm", doc_type=doc_type)
            return doc_type

    except Exception as e:
        log.warning("classify_llm_unavailable", error=str(e)[:150])

    return "unknown"
