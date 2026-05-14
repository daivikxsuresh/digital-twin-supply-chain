"""
Async Kafka producer.
Wraps confluent-kafka's synchronous Producer in a thread-pool executor
so it can be awaited from async code without blocking the event loop.
Retries delivery failures with exponential backoff (max 5 attempts).
"""

import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Any

import structlog
from confluent_kafka import Producer as _Producer

from app.config import settings
from app.ingest import topics as T

logger = structlog.get_logger(__name__)

_RETRY_BASE_SECONDS = 0.25
_MAX_RETRIES = 5


class _DeliveryFuture:
    """Bridges confluent-kafka's callback-based delivery to an asyncio Future."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._future: asyncio.Future = loop.create_future()

    def callback(self, err, msg) -> None:
        if err:
            self._loop.call_soon_threadsafe(
                self._future.set_exception, RuntimeError(str(err))
            )
        else:
            self._loop.call_soon_threadsafe(self._future.set_result, msg)

    async def wait(self) -> Any:
        return await self._future


class AsyncProducer:
    """
    Thread-safe async Kafka producer.
    One shared instance per process — obtain via get_producer().
    """

    def __init__(self) -> None:
        self._producer = _Producer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "acks": "all",
                "retries": 3,
                "retry.backoff.ms": 250,
                "delivery.timeout.ms": 10_000,
            }
        )
        # Background thread keeps confluent-kafka's internal queue flushed
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        while True:
            self._producer.poll(0.1)

    async def publish(self, topic: str, key: str, payload: dict) -> None:
        """
        Publish a JSON payload to a Kafka topic.
        key should be "{source_system}:{external_id}" for consistent partition routing.
        Retries up to _MAX_RETRIES times with exponential backoff.
        """
        value = json.dumps(payload, default=str).encode()
        loop = asyncio.get_running_loop()

        for attempt in range(1, _MAX_RETRIES + 1):
            future = _DeliveryFuture(loop)
            self._producer.produce(
                topic=topic,
                key=key.encode(),
                value=value,
                callback=future.callback,
            )
            try:
                await future.wait()
                logger.debug("kafka.published", topic=topic, key=key)
                return
            except RuntimeError as exc:
                if attempt == _MAX_RETRIES:
                    logger.error("kafka.publish_failed", topic=topic, key=key, error=str(exc))
                    raise
                wait = _RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "kafka.publish_retry",
                    topic=topic,
                    key=key,
                    attempt=attempt,
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)

    async def publish_event(
        self,
        event_type: str,
        source_system: str,
        external_id: str,
        topic: str,
        payload: dict,
    ) -> None:
        """Wraps a payload in the canonical CanonicalEvent envelope and publishes it."""
        import uuid

        envelope = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "source_system": source_system,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        key = f"{source_system}:{external_id}"
        await self.publish(topic, key, envelope)

    async def publish_to_dlq(self, original_event: dict, error: str, source_topic: str) -> None:
        """Route a failed/malformed event to the dead-letter queue."""
        import traceback as tb

        dlq_payload = {
            "original_event": original_event,
            "error": error,
            "source_topic": source_topic,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        key = original_event.get("event_id", "unknown")
        await self.publish(T.DLQ, key, dlq_payload)
        logger.warning("kafka.dlq_routed", source_topic=source_topic, key=key, error=error)

    async def flush(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._producer.flush, 10)


# Module-level singleton — import and use directly
_producer_instance: AsyncProducer | None = None
_producer_lock = threading.Lock()


def get_producer() -> AsyncProducer:
    global _producer_instance
    if _producer_instance is None:
        with _producer_lock:
            if _producer_instance is None:
                _producer_instance = AsyncProducer()
    return _producer_instance
