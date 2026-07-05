from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import structlog

from config import settings

log = structlog.get_logger()

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGO_URI)
    _db = _client[settings.MONGO_DB]
    # Verify connection
    await _client.admin.command("ping")
    log.info("mongodb_connected", uri=settings.MONGO_URI, db=settings.MONGO_DB)


async def disconnect_db() -> None:
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        log.info("mongodb_disconnected")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _db


async def create_indexes() -> None:
    db = get_db()

    await db.jobs.create_index("job_id", unique=True)
    await db.jobs.create_index("status")
    await db.jobs.create_index("uploaded_at")
    await db.jobs.create_index("doc_type")

    await db.ocr_pages.create_index([("job_id", 1), ("page", 1)], unique=True)
    await db.ocr_pages.create_index("job_id")
    await db.ocr_pages.create_index("status")
    await db.ocr_pages.create_index("ocr_source")
    await db.ocr_pages.create_index("is_handwritten")

    await db.extracted_data.create_index("job_id", unique=True)
    await db.extracted_data.create_index("doc_type")

    await db.failed_jobs.create_index("job_id")
    await db.failed_jobs.create_index("failed_at")

    log.info("mongodb_indexes_created")
