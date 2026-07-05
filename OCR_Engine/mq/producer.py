import structlog
from datetime import datetime

from mq.redis_client import get_redis
from mq.streams import STREAM_DEAD_LETTER
from config import settings

log = structlog.get_logger()


async def push_to_stream(stream: str, data: dict) -> str:
    """Add a message to a Redis Stream. Returns the message ID."""
    r = get_redis()
    msg_id = await r.xadd(
        stream,
        data,
        maxlen=settings.REDIS_STREAM_MAX_LEN,
        approximate=True,
    )
    log.debug("stream_push", stream=stream, msg_id=msg_id,
              job_id=data.get("job_id"))
    return msg_id


async def push_to_dlq(data: dict, error: str) -> str:
    """Push a failed message to the Dead Letter Queue."""
    r = get_redis()
    dlq_data = {
        **data,
        "dlq_error": error,
        "dlq_timestamp": datetime.utcnow().isoformat(),
    }
    msg_id = await r.xadd(
        STREAM_DEAD_LETTER,
        dlq_data,
        maxlen=settings.REDIS_STREAM_MAX_LEN,
        approximate=True,
    )
    log.warning("dlq_push", stream=STREAM_DEAD_LETTER, msg_id=msg_id,
                job_id=data.get("job_id"), error=error)
    return msg_id
