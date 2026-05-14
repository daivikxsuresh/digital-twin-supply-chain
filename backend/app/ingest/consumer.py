"""
Base Kafka consumer.
Subclass this and implement process() to build a processor.

Guarantees:
- Offsets committed only after successful process() call
- Failed messages routed to DLQ (offset still committed to avoid infinite retry)
- Graceful shutdown on asyncio.CancelledError
- All exceptions logged with full context
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

import structlog
from confluent_kafka import Consumer, KafkaError, KafkaException, Message

from app.config import settings
from app.ingest import topics as T

logger = structlog.get_logger(__name__)


class BaseConsumer(ABC):
    """
    Async consumer base class.
    Runs as a background asyncio task — one instance per processor.
    confluent-kafka's blocking poll() runs in a thread-pool executor.
    """

    # Override in subclass
    group_id: str = settings.kafka_consumer_group
    poll_timeout: float = 1.0

    def __init__(self, topics: list[str]) -> None:
        self._topics = topics
        self._consumer = Consumer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "group.id": self.group_id,
                "auto.offset.reset": "earliest",
                # Manual commit — we commit only after successful process()
                "enable.auto.commit": False,
                "session.timeout.ms": 30_000,
                "max.poll.interval.ms": 300_000,
            }
        )
        self._consumer.subscribe(topics)
        self._running = False

    @abstractmethod
    async def process(self, event: dict, raw_message: Message) -> None:
        """
        Process a single deserialized event dict.
        Raise any exception to trigger DLQ routing for this message.
        """
        ...

    async def consume_loop(self) -> None:
        """
        Main loop. Run as an asyncio background task.
        Exits cleanly when cancelled.
        """
        self._running = True
        loop = asyncio.get_running_loop()
        log = logger.bind(consumer=self.__class__.__name__, topics=self._topics)
        log.info("consumer.started")

        try:
            while self._running:
                msg: Message | None = await loop.run_in_executor(
                    None, self._consumer.poll, self.poll_timeout
                )

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    log.error("consumer.kafka_error", error=str(msg.error()))
                    continue

                raw_value = msg.value()
                topic = msg.topic()

                try:
                    event = json.loads(raw_value)
                except json.JSONDecodeError as exc:
                    log.error("consumer.json_decode_error", topic=topic, error=str(exc))
                    await self._send_to_dlq({"raw": raw_value.decode(errors="replace")}, str(exc), topic)
                    self._consumer.commit(message=msg, asynchronous=False)
                    continue

                try:
                    await self.process(event, msg)
                    self._consumer.commit(message=msg, asynchronous=False)
                    log.debug(
                        "consumer.processed",
                        topic=topic,
                        event_id=event.get("event_id"),
                        event_type=event.get("event_type"),
                    )
                except Exception as exc:
                    log.error(
                        "consumer.process_error",
                        topic=topic,
                        event_id=event.get("event_id"),
                        error=str(exc),
                        exc_info=True,
                    )
                    await self._send_to_dlq(event, str(exc), topic)
                    # Commit anyway — malformed events must not block the partition
                    self._consumer.commit(message=msg, asynchronous=False)

        except asyncio.CancelledError:
            log.info("consumer.stopping")
        finally:
            self._consumer.close()
            log.info("consumer.closed")

    async def _send_to_dlq(self, event: dict, error: str, source_topic: str) -> None:
        from app.ingest.producer import get_producer
        try:
            await get_producer().publish_to_dlq(event, error, source_topic)
        except Exception as exc:
            logger.error("consumer.dlq_failed", error=str(exc))

    def stop(self) -> None:
        self._running = False
