import asyncio
import structlog
from abc import ABC, abstractmethod

from mq.consumer import BaseConsumer
from mq.producer import push_to_stream, push_to_dlq

log = structlog.get_logger()


class BaseWorker(ABC):
    """
    Base class for all pipeline workers.
    Subclasses implement process_message() only.
    Handles run loop, error handling, retry with backoff, and DLQ routing.
    """

    consumer_stream: str
    consumer_group: str = "ocr-service"
    consumer_name: str = ""

    def __init__(self):
        self.consumer_name = self.__class__.__name__
        self.logger = structlog.get_logger().bind(worker=self.consumer_name)
        self.consumer = BaseConsumer(
            stream=self.consumer_stream,
            group=self.consumer_group,
            consumer_name=self.consumer_name,
        )

    @abstractmethod
    async def process_message(self, msg: dict) -> None:
        """Process a single message from the stream."""

    async def run(self):
        """Main worker loop. Called once as an asyncio Task."""
        await self.consumer.ensure_group_exists()
        self.logger.info("worker_started", stream=self.consumer_stream)

        while True:
            try:
                messages = await self.consumer.read_batch(batch_size=10, block_ms=2000)

                if not messages:
                    await asyncio.sleep(0.1)
                    continue

                tasks = [self._handle_one(msg) for msg in messages]
                await asyncio.gather(*tasks, return_exceptions=True)

                await self.consumer.reclaim_stale(min_idle_ms=300_000)

            except asyncio.CancelledError:
                self.logger.info("worker_stopping")
                break
            except Exception as e:
                self.logger.error("worker_loop_error", error=str(e))
                await asyncio.sleep(1)

    async def _handle_one(self, msg: dict):
        msg_id = msg["id"]
        retry_count = int(msg["data"].get("retry_count", 0))

        try:
            await self.process_message(msg["data"])
            await self.consumer.ack(msg_id)

        except Exception as e:
            self.logger.warning("message_failed",
                                msg_id=msg_id, retry=retry_count, error=str(e),
                                job_id=msg["data"].get("job_id"),
                                msg_keys=list(msg["data"].keys()))

            if retry_count < 3:
                msg["data"]["retry_count"] = str(retry_count + 1)
                await asyncio.sleep(2 ** retry_count)
                await push_to_stream(self.consumer_stream, msg["data"])
                await self.consumer.ack(msg_id)
            else:
                await push_to_dlq(msg["data"], error=str(e))
                await self.consumer.ack(msg_id)
                self.logger.error("message_dlq", msg_id=msg_id,
                                  job_id=msg["data"].get("job_id"))
