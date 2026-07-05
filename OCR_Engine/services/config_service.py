"""
Configuration service: load/save/apply config from MongoDB with history tracking.
MongoDB is the source of truth for runtime settings.
"""
from datetime import datetime
from typing import Any
import structlog

from db.mongo import get_db
from config import settings

log = structlog.get_logger()

CONFIG_DOC_ID = "current"
COLLECTION_CONFIG = "app_config"
COLLECTION_CONFIG_HISTORY = "app_config_history"

# Configuration schema grouped by category
CONFIG_SCHEMA = {
    "models": {
        "OLLAMA_BASE_URL": {"type": "str", "label": "Ollama Base URL", "desc": "HTTP endpoint for Ollama API"},
        "QWEN_VL_MODEL": {"type": "str", "label": "Vision/VL Model", "desc": "Ollama model for handwriting OCR (must support images)"},
        "EXTRACTION_MODEL": {"type": "str", "label": "Extraction Model", "desc": "Ollama model for structured data extraction"},
        "PADDLE_LANG": {"type": "str", "label": "PaddleOCR Default Language", "desc": "Default language for PaddleOCR (en, hi, ta, te, kn)"},
        "PADDLE_USE_GPU": {"type": "bool", "label": "PaddleOCR GPU Mode", "desc": "Use GPU for PaddleOCR inference"},
        "INDICTRANS2_MODEL_PATH": {"type": "str", "label": "IndicTrans2 Model Path", "desc": "Path to IndicTrans2 translation model"},
        "FASTTEXT_MODEL_PATH": {"type": "str", "label": "fastText Model Path", "desc": "Path to fastText language detection model"},
    },
    "ocr_thresholds": {
        "PADDLE_CONFIDENCE_THRESHOLD": {"type": "float", "label": "PaddleOCR Confidence Threshold", "desc": "Below this → fallback to VL model (0.0-1.0)", "min": 0.0, "max": 1.0},
        "PADDLE_DET_DB_THRESH": {"type": "float", "label": "Detection DB Threshold", "desc": "PaddleOCR text detection threshold", "min": 0.0, "max": 1.0},
        "PADDLE_DET_DB_BOX_THRESH": {"type": "float", "label": "Detection Box Threshold", "desc": "PaddleOCR bounding box threshold", "min": 0.0, "max": 1.0},
    },
    "preprocessing": {
        "PREPROCESS_TARGET_DPI": {"type": "int", "label": "Target DPI", "desc": "Normalize images to this DPI (150-600)", "min": 150, "max": 600},
        "PREPROCESS_HANDWRITING_MODE": {"type": "bool", "label": "Handwriting Mode", "desc": "Enable handwriting-optimized preprocessing pipeline"},
        "PREPROCESS_SAVE_INTERMEDIATE": {"type": "bool", "label": "Save Debug Images", "desc": "Save intermediate preprocessing steps for debugging"},
    },
    "workers": {
        "OCR_BATCH_SIZE": {"type": "int", "label": "OCR Batch Size", "desc": "Pages per OCR batch", "min": 1, "max": 64},
        "QWEN_VL_BATCH_SIZE": {"type": "int", "label": "VL Batch Size", "desc": "Pages per VL model batch", "min": 1, "max": 16},
        "TRANSLATION_BATCH_SIZE": {"type": "int", "label": "Translation Batch Size", "desc": "Texts per translation batch", "min": 1, "max": 64},
        "RENDER_BATCH_SIZE": {"type": "int", "label": "Render Batch Size", "desc": "PDF pages per render batch", "min": 1, "max": 50},
        "WORKER_CONCURRENCY": {"type": "int", "label": "Worker Concurrency", "desc": "Async tasks per worker type", "min": 1, "max": 16},
        "MAX_QUEUE_DEPTH": {"type": "int", "label": "Max Queue Depth", "desc": "Maximum messages per stream before backpressure", "min": 100, "max": 1000000},
    },
    "storage": {
        "NFS_BASE_PATH": {"type": "str", "label": "Base Storage Path", "desc": "Root path for all file storage"},
        "NFS_INCOMING_PATH": {"type": "str", "label": "Incoming Path", "desc": "Upload destination directory"},
        "NFS_PROCESSED_PATH": {"type": "str", "label": "Processed Path", "desc": "Completed files directory"},
        "NFS_FAILED_PATH": {"type": "str", "label": "Failed Path", "desc": "Failed processing directory"},
        "NFS_ARCHIVE_PATH": {"type": "str", "label": "Archive Path", "desc": "Deleted job archives"},
    },
    "infrastructure": {
        "MONGO_URI": {"type": "str", "label": "MongoDB URI", "desc": "MongoDB connection string", "sensitive": True},
        "REDIS_URL": {"type": "str", "label": "Redis URL", "desc": "Redis connection string", "sensitive": True},
        "REDIS_STREAM_MAX_LEN": {"type": "int", "label": "Stream Max Length", "desc": "Max messages per Redis stream", "min": 1000, "max": 10000000},
        "LOG_LEVEL": {"type": "str", "label": "Log Level", "desc": "Application log level", "options": ["DEBUG", "INFO", "WARNING", "ERROR"]},
    },
    "upload_limits": {
        "MAX_UPLOAD_SIZE_MB": {"type": "int", "label": "Max Upload Size (MB)", "desc": "Maximum single file upload size", "min": 1, "max": 5000},
        "MAX_BULK_FILES": {"type": "int", "label": "Max Bulk Files", "desc": "Maximum files per bulk upload", "min": 1, "max": 500},
    },
}


def _get_defaults() -> dict:
    """Get all default settings from the .env-loaded Settings object."""
    result = {}
    for category, fields in CONFIG_SCHEMA.items():
        result[category] = {}
        for key in fields:
            result[category][key] = getattr(settings, key, None)
    return result


def _flatten_config(grouped: dict) -> dict:
    """Flatten grouped config into a flat dict of {KEY: value}."""
    flat = {}
    for category, fields in grouped.items():
        if isinstance(fields, dict):
            for key, value in fields.items():
                flat[key] = value
    return flat


async def load_config_from_db() -> dict | None:
    """Load saved config from MongoDB. Returns None if no saved config exists."""
    db = get_db()
    doc = await db[COLLECTION_CONFIG].find_one({"_id": CONFIG_DOC_ID})
    if doc:
        doc.pop("_id", None)
        return doc
    return None


async def save_config_to_db(config: dict, updated_by: str = "admin") -> None:
    """Save config to MongoDB and record history."""
    db = get_db()

    # Add metadata
    config["updated_at"] = datetime.utcnow()
    config["updated_by"] = updated_by

    # Upsert the current config
    await db[COLLECTION_CONFIG].replace_one(
        {"_id": CONFIG_DOC_ID},
        {**config, "_id": CONFIG_DOC_ID},
        upsert=True
    )

    # Record in history
    history_entry = {
        **config,
        "saved_at": datetime.utcnow(),
        "saved_by": updated_by,
    }
    await db[COLLECTION_CONFIG_HISTORY].insert_one(history_entry)

    log.info("config_saved", updated_by=updated_by)


async def get_current_config() -> dict:
    """Get current active config (from DB if exists, else defaults)."""
    db_config = await load_config_from_db()
    if db_config:
        return db_config
    return _get_defaults()


async def update_config(updates: dict, updated_by: str = "admin") -> dict:
    """
    Partially update config. Merges updates into existing config.
    Applies changes to live settings immediately.
    """
    current = await get_current_config()

    # Merge updates into current config
    for category, fields in updates.items():
        if category in CONFIG_SCHEMA and isinstance(fields, dict):
            if category not in current:
                current[category] = {}
            current[category].update(fields)

    # Remove metadata before saving
    current.pop("updated_at", None)
    current.pop("updated_by", None)

    # Save to DB
    await save_config_to_db(current, updated_by)

    # Apply to live settings
    apply_config_to_settings(current)

    return current


async def reset_config() -> dict:
    """Reset config to .env defaults and delete DB config."""
    db = get_db()
    await db[COLLECTION_CONFIG].delete_one({"_id": CONFIG_DOC_ID})

    defaults = _get_defaults()
    apply_config_to_settings(defaults)

    # Record reset in history
    await db[COLLECTION_CONFIG_HISTORY].insert_one({
        "action": "reset_to_defaults",
        "saved_at": datetime.utcnow(),
        "saved_by": "admin",
    })

    log.info("config_reset_to_defaults")
    return defaults


async def get_config_history(limit: int = 20) -> list:
    """Get recent config change history."""
    db = get_db()
    cursor = db[COLLECTION_CONFIG_HISTORY].find(
        {}, {"_id": 0}
    ).sort("saved_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


def apply_config_to_settings(config: dict) -> None:
    """Apply grouped config dict to the live settings object."""
    flat = _flatten_config(config)
    for key, value in flat.items():
        if hasattr(settings, key) and value is not None:
            try:
                current_type = type(getattr(settings, key))
                casted = current_type(value)
                object.__setattr__(settings, key, casted)
            except (ValueError, TypeError) as e:
                log.warning("config_apply_failed", key=key, value=value, error=str(e))


def get_config_schema() -> dict:
    """Return the full config schema for the UI to render forms."""
    return CONFIG_SCHEMA
