import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pathlib import Path

from services.config_service import (
    get_current_config,
    update_config,
    reset_config,
    get_config_history,
    get_config_schema,
)
from config import settings
import structlog

log = structlog.get_logger()

router = APIRouter()

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


@router.get("/admin/config")
async def get_config():
    """Get all current active settings grouped by category."""
    config = await get_current_config()
    schema = get_config_schema()
    return {
        "config": config,
        "schema": schema,
    }


@router.put("/admin/config")
async def update_config_endpoint(body: dict):
    """
    Partially update config settings. Body should be grouped by category:
    {"models": {"QWEN_VL_MODEL": "qwen2.5-vl:3b"}, "ocr_thresholds": {...}}
    """
    try:
        updated = await update_config(body)
        return {"status": "saved", "config": updated}
    except Exception as e:
        log.error("config_update_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/config/reset")
async def reset_config_endpoint():
    """Reset all settings to .env defaults."""
    defaults = await reset_config()
    return {"status": "reset", "config": defaults}


@router.get("/admin/config/history")
async def config_history(limit: int = 20):
    """Get recent config change history."""
    history = await get_config_history(limit)
    # Convert datetime objects to strings for JSON
    for entry in history:
        for key, val in entry.items():
            if hasattr(val, "isoformat"):
                entry[key] = val.isoformat()
    return {"history": history}


@router.get("/admin/models")
async def list_ollama_models():
    """List all models available in the connected Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [
                {
                    "name": m["name"],
                    "size_gb": round(m.get("size", 0) / (1024**3), 2),
                    "modified": m.get("modified_at", ""),
                }
                for m in data.get("models", [])
            ]
            return {"models": models, "ollama_url": settings.OLLAMA_BASE_URL}
    except Exception as e:
        return {"models": [], "error": str(e), "ollama_url": settings.OLLAMA_BASE_URL}


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve the admin configuration dashboard."""
    template_path = TEMPLATES_DIR / "admin.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Admin template not found")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
