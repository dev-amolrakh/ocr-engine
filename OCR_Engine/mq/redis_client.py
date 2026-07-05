import redis.asyncio as redis
import structlog

from config import settings

log = structlog.get_logger()

_pool: redis.Redis | None = None


async def connect_redis() -> None:
    global _pool
    _pool = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
    )
    await _pool.ping()
    log.info("redis_connected", url=settings.REDIS_URL)


async def disconnect_redis() -> None:
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None
        log.info("redis_disconnected")


def get_redis() -> redis.Redis:
    if _pool is None:
        raise RuntimeError("Redis not connected. Call connect_redis() first.")
    return _pool
