from db.mongo import get_db
from mq.redis_client import get_redis


async def get_database():
    """Dependency: get MongoDB database instance."""
    return get_db()


async def get_redis_client():
    """Dependency: get Redis client instance."""
    return get_redis()
