import structlog

from mq.redis_client import get_redis

log = structlog.get_logger()


class BaseConsumer:
    """
    Redis Streams consumer using consumer groups.
    Provides at-least-once delivery with ack/nack and stale message reclaim.
    """

    def __init__(self, stream: str, group: str, consumer_name: str):
        self.stream = stream
        self.group = group
        self.consumer_name = consumer_name

    async def ensure_group_exists(self) -> None:
        """Create the consumer group if it doesn't exist."""
        r = get_redis()
        try:
            await r.xgroup_create(self.stream, self.group, id="0", mkstream=True)
            log.info("consumer_group_created",
                     stream=self.stream, group=self.group)
        except Exception as e:
            if "BUSYGROUP" in str(e):
                pass  # Group already exists
            else:
                raise

    async def read_batch(self, batch_size: int = 10, block_ms: int = 2000) -> list[dict]:
        """
        Read a batch of messages from the stream using XREADGROUP.
        Returns list of dicts: [{"id": msg_id, "data": {field: value}}]
        """
        r = get_redis()
        response = await r.xreadgroup(
            groupname=self.group,
            consumername=self.consumer_name,
            streams={self.stream: ">"},
            count=batch_size,
            block=block_ms,
        )

        if not response:
            return []

        messages = []
        for _stream_name, entries in response:
            for msg_id, fields in entries:
                messages.append({"id": msg_id, "data": fields})

        return messages

    async def ack(self, msg_id: str) -> None:
        """Acknowledge a processed message."""
        r = get_redis()
        await r.xack(self.stream, self.group, msg_id)

    async def reclaim_stale(self, min_idle_ms: int = 300_000) -> list[dict]:
        """
        Reclaim messages that have been pending for too long (crashed consumers).
        Returns reclaimed messages in the same format as read_batch.
        """
        r = get_redis()
        try:
            result = await r.xautoclaim(
                name=self.stream,
                groupname=self.group,
                consumername=self.consumer_name,
                min_idle_time=min_idle_ms,
                start_id="0-0",
                count=10,
            )
            if not result or len(result) < 2:
                return []

            _new_start, entries = result[0], result[1]
            messages = []
            for msg_id, fields in entries:
                if fields:
                    messages.append({"id": msg_id, "data": fields})
            return messages
        except Exception as e:
            log.debug("reclaim_error", error=str(e))
            return []
