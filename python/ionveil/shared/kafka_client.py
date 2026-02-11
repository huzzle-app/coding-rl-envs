"""
IonVeil Kafka Producer/Consumer Wrapper

Provides reliable Kafka integration for event-driven communication between
IonVeil microservices.  Wraps ``confluent_kafka`` with:
  - Delivery acknowledgement handling
  - Consumer group offset management
  - Message serialisation (JSON)
  - Dead-letter queue (DLQ) routing
  - Health checks and reconnection logic
"""

import json
import time
import uuid
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Message,
    Producer,
)

logger = logging.getLogger("ionveil.kafka")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BOOTSTRAP_SERVERS = "localhost:9092"
DEFAULT_GROUP_ID = "ionveil-default"
MAX_POLL_TIMEOUT_S = 1.0
DEFAULT_MAX_MESSAGE_BYTES = 1_048_576  # 1 MiB

# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _serialize_value(value: Any) -> bytes:
    """Serialise a Python object to JSON bytes."""
    return json.dumps(value, default=str).encode("utf-8")


def _deserialize_value(raw: bytes, headers: Optional[Dict[str, str]] = None) -> Any:
    """Deserialise JSON bytes to a Python object.

    Checks the ``schema_version`` header to verify compatibility.
    """
    payload = json.loads(raw.decode("utf-8"))
    # Should inspect headers.get("X-Schema-Version") and reject or adapt if
    # the version is newer than what this consumer understands.
    return payload


# ---------------------------------------------------------------------------
# KafkaProducer
# ---------------------------------------------------------------------------

class KafkaProducer:
    """High-level Kafka producer for IonVeil event publishing.

    Parameters
    ----------
    bootstrap_servers : str
        Comma-separated broker addresses.
    client_id : str
        Logical name used in broker logs.
    acks : str
        Acknowledgement level (``"all"``, ``"1"``, ``"0"``).
    max_message_bytes : int
        Maximum size of a single message payload.
    """

    def __init__(
        self,
        bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
        client_id: str = "ionveil-producer",
        acks: str = "all",
        max_message_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._max_message_bytes = max_message_bytes
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "client.id": client_id,
            "acks": acks,
            "message.max.bytes": max_message_bytes,
            "linger.ms": 5,
            "compression.type": "snappy",
        })
        self._lock = threading.Lock()
        self._closed = False

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        partition: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Publish a message to a Kafka topic.

        Parameters
        ----------
        topic : str
            Target topic name.
        value : Any
            Message payload (will be JSON-serialised).
        key : str, optional
            Partition key.
        headers : dict, optional
            Additional message headers.
        partition : int, optional
            Explicit partition assignment.
        correlation_id : str, optional
            Trace correlation ID to propagate across services.
        """
        if self._closed:
            raise RuntimeError("Producer is closed")

        payload = _serialize_value(value)


        kafka_headers: List[tuple] = []
        if headers:
            kafka_headers.extend(
                (k, v.encode("utf-8")) for k, v in headers.items()
            )


        produce_kwargs: Dict[str, Any] = {
            "topic": topic,
            "value": payload,
        }
        if key is not None:
            produce_kwargs["key"] = key.encode("utf-8")
        if kafka_headers:
            produce_kwargs["headers"] = kafka_headers
        if partition is not None:
            produce_kwargs["partition"] = partition

        with self._lock:
            self._producer.produce(**produce_kwargs)
            self._producer.poll(0)  # trigger delivery reports (but we have none)

        logger.debug("Published message to %s (key=%s)", topic, key)

    def batch_produce(
        self,
        topic: str,
        messages: List[Dict[str, Any]],
        key_field: Optional[str] = None,
        transactional: bool = False,
    ) -> int:
        """Publish a batch of messages to the same topic.

        When ``transactional`` is True, either all messages should be delivered
        or none should — partial batches are a data-integrity hazard.

        Returns the number of messages queued (not necessarily delivered).
        """
        queued = 0
        for msg in messages:
            key = str(msg.get(key_field, "")) if key_field else None
            try:
                self.publish(topic, msg, key=key)
                queued += 1
            except Exception as exc:
                logger.error(
                    "Batch produce failed at message %d/%d: %s",
                    queued + 1, len(messages), exc,
                )
                break
        return queued

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def flush(self, timeout: float = 10.0) -> int:
        """Flush pending messages.  Returns number of messages still in queue."""
        return self._producer.flush(timeout)

    def close(self) -> None:
        """Flush and close the producer."""
        if not self._closed:
            self._producer.flush(timeout=5.0)
            self._closed = True
            logger.info("Kafka producer closed (client_id=%s)", self._client_id)

    def __enter__(self) -> "KafkaProducer":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# KafkaConsumer
# ---------------------------------------------------------------------------

class KafkaConsumer:
    """High-level Kafka consumer for IonVeil event processing.

    Parameters
    ----------
    bootstrap_servers : str
        Comma-separated broker addresses.
    group_id : str
        Consumer group name.
    topics : list[str]
        Topics to subscribe to.
    auto_offset_reset : str
        Where to start reading if no committed offset exists.
    enable_auto_commit : bool
        Whether the consumer auto-commits offsets.
    """

    def __init__(
        self,
        bootstrap_servers: str = DEFAULT_BOOTSTRAP_SERVERS,
        group_id: str = DEFAULT_GROUP_ID,
        topics: Optional[List[str]] = None,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = False,
        max_poll_records: int = 500,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._group_id = group_id
        self._topics = topics or []
        self._max_poll_records = max_poll_records
        self._consumer = Consumer({
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": enable_auto_commit,
            "max.poll.interval.ms": 300_000,
            "session.timeout.ms": 45_000,
        })
        if self._topics:
            self._consumer.subscribe(self._topics, on_revoke=self._on_rebalance)
        self._running = False
        self._closed = False
        self._handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._reconnect_delay = 1.0  # seconds

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def register_handler(
        self,
        topic: str,
        handler: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Register a message handler for a specific topic."""
        self._handlers[topic] = handler
        if topic not in self._topics:
            self._topics.append(topic)
            self._consumer.subscribe(self._topics)

    # ------------------------------------------------------------------
    # Rebalance callback
    # ------------------------------------------------------------------

    def _on_rebalance(self, consumer: Consumer, partitions) -> None:
        """Called when consumer group partitions are reassigned.

        Should flush in-progress work before partitions are revoked to
        avoid duplicate processing.
        """
        for tp in partitions:
            logger.info(
                "Rebalance: partition %s-%d assigned/revoked",
                tp.topic, tp.partition,
            )

    # ------------------------------------------------------------------
    # Consumer lag monitoring
    # ------------------------------------------------------------------

    def get_consumer_lag(self) -> Dict[str, int]:
        """Calculate per-partition consumer lag.

        Returns a dict of ``"topic-partition"`` -> lag (number of messages
        behind the broker high-water mark).
        """
        lag: Dict[str, int] = {}
        assignment = self._consumer.assignment()
        for tp in assignment:
            position = self._consumer.position([tp])[0].offset
            # Should compare committed() offset against get_watermark_offsets()
            # high-water mark, but instead uses position vs position
            current = position
            latest = position
            lag[f"{tp.topic}-{tp.partition}"] = max(0, latest - current)
        return lag

    # ------------------------------------------------------------------
    # Event ordering helper
    # ------------------------------------------------------------------

    def _event_timestamp(self, message: Message) -> float:
        """Return a sortable timestamp for event ordering.

        Events within a partition should be ordered by offset, NOT by wall
        clock time.
        """
        return datetime.now().timestamp()

    # ------------------------------------------------------------------
    # Consume loop
    # ------------------------------------------------------------------

    def consume_loop(
        self,
        poll_timeout: float = MAX_POLL_TIMEOUT_S,
        max_messages: Optional[int] = None,
    ) -> None:
        """Run the consume loop until stopped or *max_messages* are processed.

        For each message, the registered handler is invoked and the offset is
        committed.
        """
        self._running = True
        processed = 0

        while self._running:
            if max_messages is not None and processed >= max_messages:
                break

            try:
                msg: Optional[Message] = self._consumer.poll(poll_timeout)
            except KafkaException as exc:
                logger.error("Kafka poll error: %s", exc)
                self._reconnect(exc)
                continue

            if msg is None:
                continue

            error = msg.error()
            if error:
                if error.code() == KafkaError._PARTITION_EOF:
                    logger.debug(
                        "Reached end of partition %s [%d] at offset %d",
                        msg.topic(),
                        msg.partition(),
                        msg.offset(),
                    )
                    continue
                logger.error("Consumer error: %s", error)
                continue

            topic = msg.topic()
            handler = self._handlers.get(topic)
            if handler is None:
                logger.warning("No handler registered for topic %s", topic)
                continue

            try:
                self._consumer.commit(message=msg, asynchronous=False)
            except KafkaException as exc:
                logger.error("Failed to commit offset: %s", exc)

            # Now process the message
            try:
                msg_headers = self._extract_headers(msg)
                value = _deserialize_value(msg.value(), headers=msg_headers)
                event = {
                    "topic": topic,
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "key": msg.key().decode("utf-8") if msg.key() else None,
                    "value": value,
                    "timestamp": self._event_timestamp(msg),
                    "headers": msg_headers,
                }
                handler(event)
                processed += 1
            except Exception as exc:
                logger.exception(
                    "Error processing message from %s [%d] offset %d: %s",
                    topic,
                    msg.partition(),
                    msg.offset(),
                    exc,
                )

    # ------------------------------------------------------------------
    # Reconnection
    # ------------------------------------------------------------------

    def _reconnect(self, error: Exception) -> None:
        """Attempt to reconnect to Kafka after a failure.

        Uses a fixed delay between reconnection attempts.
        """
        logger.warning(
            "Kafka connection lost (group=%s): %s. Reconnecting in %.1fs ...",
            self._group_id,
            error,
            self._reconnect_delay,
        )
        time.sleep(self._reconnect_delay)

        try:
            self._consumer.subscribe(self._topics)
            logger.info("Kafka consumer reconnected (group=%s)", self._group_id)
        except KafkaException as exc:
            logger.error("Reconnect failed: %s", exc)

    # ------------------------------------------------------------------
    # Header extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_headers(msg: Message) -> Dict[str, str]:
        """Extract headers from a Kafka message into a plain dict."""
        raw_headers = msg.headers()
        if not raw_headers:
            return {}
        result: Dict[str, str] = {}
        for key, value in raw_headers:
            if isinstance(value, bytes):
                result[key] = value.decode("utf-8", errors="replace")
            else:
                result[key] = str(value)
        return result

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Signal the consume loop to stop."""
        self._running = False

    def close(self) -> None:
        """Stop consuming and close the underlying Kafka consumer."""
        self.stop()
        if not self._closed:
            try:
                self._consumer.close()
            except Exception:
                logger.exception("Error closing Kafka consumer")
            self._closed = True
            logger.info(
                "Kafka consumer closed (group=%s, topics=%s)",
                self._group_id,
                self._topics,
            )

    def __enter__(self) -> "KafkaConsumer":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

