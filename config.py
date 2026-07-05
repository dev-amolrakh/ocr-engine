from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ocr-service"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "ocr_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_STREAM_MAX_LEN: int = 100_000

    # NFS / Local Storage (use local paths on Windows for testing)
    NFS_BASE_PATH: str = "./storage"
    NFS_INCOMING_PATH: str = "./storage/incoming"
    NFS_PROCESSED_PATH: str = "./storage/processed"
    NFS_FAILED_PATH: str = "./storage/failed"
    NFS_ARCHIVE_PATH: str = "./storage/archive"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    QWEN_VL_MODEL: str = "qwen2.5vl:7b"
    EXTRACTION_MODEL: str = "qwen2.5:14b"

    # PaddleOCR
    PADDLE_LANG: str = "en"
    PADDLE_USE_GPU: bool = True
    PADDLE_CONFIDENCE_THRESHOLD: float = 0.75
    PADDLE_DET_DB_THRESH: float = 0.3
    PADDLE_DET_DB_BOX_THRESH: float = 0.5

    # Worker tuning
    OCR_BATCH_SIZE: int = 16
    QWEN_VL_BATCH_SIZE: int = 4
    TRANSLATION_BATCH_SIZE: int = 16
    RENDER_BATCH_SIZE: int = 10
    WORKER_CONCURRENCY: int = 4
    MAX_QUEUE_DEPTH: int = 10_000

    # IndicTrans2
    INDICTRANS2_MODEL_PATH: str = "./models/indictrans2"

    # fastText
    FASTTEXT_MODEL_PATH: str = "./models/fasttext/lid.176.bin"

    # Image preprocessing
    PREPROCESS_TARGET_DPI: int = 300
    PREPROCESS_HANDWRITING_MODE: bool = True
    PREPROCESS_SAVE_INTERMEDIATE: bool = False

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_BULK_FILES: int = 50

    class Config:
        env_file = ".env"

    def reload_from_dict(self, data: dict) -> None:
        """Update settings from a flat dictionary. Used by admin config service."""
        for key, value in data.items():
            if hasattr(self, key) and value is not None:
                try:
                    expected_type = type(getattr(self, key))
                    casted = expected_type(value)
                    object.__setattr__(self, key, casted)
                except (ValueError, TypeError):
                    pass


settings = Settings()
