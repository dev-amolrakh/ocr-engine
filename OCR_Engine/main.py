import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_client import make_asgi_app
import structlog

from api.routes import upload, jobs, results, pages, health
from api.routes import admin
from db.mongo import connect_db, disconnect_db, create_indexes
from mq.redis_client import connect_redis, disconnect_redis
from services.config_service import load_config_from_db, apply_config_to_settings
from middleware.logging import LoggingMiddleware
from middleware.error_handler import register_error_handlers
from workers.renderer_worker import RendererWorker
from workers.preprocessor_worker import PreprocessorWorker
from workers.ocr_worker import OCRWorker
from workers.langdetect_worker import LangDetectWorker
from workers.translation_worker import TranslationWorker
from workers.extraction_worker import ExtractionWorker
from workers.validation_worker import ValidationWorker
from config import settings

log = structlog.get_logger()

_background_tasks: list[asyncio.Task] = []


async def start_all_workers():
    """
    Instantiate every worker and launch their run() coroutine as asyncio Tasks.
    All workers run concurrently inside the same event loop as FastAPI.
    """
    workers = [
        RendererWorker(),
        PreprocessorWorker(),
        OCRWorker(),
        LangDetectWorker(),
        TranslationWorker(),
        ExtractionWorker(),
        ValidationWorker(),
    ]

    for worker in workers:
        task = asyncio.create_task(worker.run(), name=worker.__class__.__name__)
        _background_tasks.append(task)

    log.info("all_workers_started", count=len(workers),
             workers=[w.__class__.__name__ for w in workers])


async def stop_all_workers():
    """Gracefully cancel all worker tasks on shutdown."""
    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()
    log.info("all_workers_stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    await connect_db()
    await create_indexes()
    # Load saved config from DB (overrides .env with last saved admin settings)
    saved_config = await load_config_from_db()
    if saved_config:
        apply_config_to_settings(saved_config)
        log.info("config_loaded_from_db")
    await connect_redis()
    await start_all_workers()
    log.info("application_started", app=settings.APP_NAME)
    yield
    # ── Shutdown ──
    await stop_all_workers()
    await disconnect_db()
    await disconnect_redis()
    log.info("application_stopped")


app = FastAPI(
    title="OCR Document Processing Service",
    version="2.0.0",
    description="Production-grade offline OCR pipeline: PaddleOCR + Qwen-VL hybrid",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(LoggingMiddleware)
register_error_handlers(app)

app.include_router(upload.router, prefix="/api/v1", tags=["upload"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(results.router, prefix="/api/v1", tags=["results"])
app.include_router(pages.router, prefix="/api/v1", tags=["pages"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.DEBUG,
    )
