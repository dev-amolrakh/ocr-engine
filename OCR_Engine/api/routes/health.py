import time
import httpx
from fastapi import APIRouter

from db.mongo import get_db
from mq.redis_client import get_redis
from services.file_service import check_nfs_writable
from config import settings

router = APIRouter()


@router.get("/health")
async def health_liveness():
    """Basic liveness check."""
    return {"status": "ok"}


@router.get("/health/detailed")
async def health_detailed():
    """Detailed health check for all system components."""
    components = {}

    # MongoDB
    try:
        start = time.perf_counter()
        db = get_db()
        await db.command("ping")
        latency = round((time.perf_counter() - start) * 1000, 1)
        components["mongodb"] = {"status": "ok", "latency_ms": latency}
    except Exception as e:
        components["mongodb"] = {"status": "error", "error": str(e)}

    # Redis
    try:
        start = time.perf_counter()
        r = get_redis()
        await r.ping()
        latency = round((time.perf_counter() - start) * 1000, 1)
        components["redis"] = {"status": "ok", "latency_ms": latency}
    except Exception as e:
        components["redis"] = {"status": "error", "error": str(e)}

    # NFS
    try:
        writable = check_nfs_writable()
        components["nfs"] = {"status": "ok" if writable else "error", "writable": writable}
    except Exception as e:
        components["nfs"] = {"status": "error", "error": str(e)}

    # Ollama — Qwen-VL
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            vl_loaded = settings.QWEN_VL_MODEL in models
            components["ollama_qwen_vl"] = {"status": "ok", "model_loaded": vl_loaded}
    except Exception as e:
        components["ollama_qwen_vl"] = {"status": "error", "error": str(e)}

    # Ollama — Extraction model
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            ext_loaded = settings.EXTRACTION_MODEL in models
            components["ollama_extraction"] = {"status": "ok", "model_loaded": ext_loaded}
    except Exception as e:
        components["ollama_extraction"] = {"status": "error", "error": str(e)}

    # PaddleOCR
    try:
        from paddleocr import PaddleOCR
        components["paddleocr"] = {"status": "ok"}
    except Exception as e:
        components["paddleocr"] = {"status": "error", "error": str(e)}

    # IndicTrans2
    try:
        from pathlib import Path
        model_exists = Path(settings.INDICTRANS2_MODEL_PATH).exists()
        components["indictrans2"] = {"status": "ok" if model_exists else "unavailable"}
    except Exception as e:
        components["indictrans2"] = {"status": "error", "error": str(e)}

    # fastText
    try:
        from pathlib import Path
        ft_exists = Path(settings.FASTTEXT_MODEL_PATH).exists()
        components["fasttext"] = {"status": "ok" if ft_exists else "unavailable"}
    except Exception as e:
        components["fasttext"] = {"status": "error", "error": str(e)}

    overall = "ok" if all(
        c.get("status") == "ok" for c in components.values()
    ) else "degraded"

    return {"status": overall, "components": components}
