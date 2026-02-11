"""
SynapseNet Event Bus
Terminal Bench v2 - Kafka Event System

Contains bugs:
- J1: Trace context lost across Kafka - headers not propagated
- J2: Log correlation ID mismatch - different IDs in producer/consumer
- D4: Outbox pattern message loss - events published but not committed
"""
import json
import time
import uuid
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base event class for Kafka messages."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    source_service: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())  
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
    
    trace_context: Dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize event to JSON."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Event":
        """Deserialize event from JSON."""
        parsed = json.loads(data)
        return cls(**parsed)


class EventBus:
    """
    Kafka event bus for inter-service communication.

    BUG J1: Trace context (trace-id, span-id) is lost when publishing to Kafka.
            The producer does not set trace headers on messages.
    BUG J2: Log correlation IDs are generated fresh on the consumer side
            instead of being extracted from the message headers.
    BUG D4: Events are published to Kafka before the database transaction commits.
            If the transaction rolls back, the event is already published.
    """

    def __init__(self, bootstrap_servers: str = "kafka:29092", service_name: str = "unknown"):
        self.bootstrap_servers = bootstrap_servers
        self.service_name = service_name
        self._handlers: Dict[str, List[Callable]] = {}
        self._published_events: List[Event] = []

    def publish(
        self,
        topic: str,
        event: Event,
        trace_context: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Publish an event to Kafka.

        BUG J1: trace_context is accepted but never set as Kafka message headers.
        BUG D4: This is called inside a DB transaction, but the Kafka publish
                happens immediately, not after commit. If the transaction fails,
                the event is already on Kafka.
        """
        event.source_service = self.service_name
        
        # Should be: headers = [("trace-id", trace_context.get("trace_id", "").encode())]

        
        correlation_id = str(uuid.uuid4())  # Should extract from trace_context
        event.metadata["correlation_id"] = correlation_id

        logger.info(
            f"Publishing event {event.event_type} to {topic}",
            extra={"correlation_id": correlation_id}
        )

        try:
            
            # Should use outbox pattern: write to outbox table, then publish asynchronously
            self._published_events.append(event)
            return True
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            return False

    def subscribe(self, topic: str, handler: Callable[[Event], None]):
        """Subscribe to events on a topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    def consume(self, topic: str, timeout: float = 1.0) -> Optional[Event]:
        """
        Consume an event from Kafka.

        BUG J2: Generates a fresh correlation ID instead of extracting from headers.
        """
        # Simulated consumption
        if self._published_events:
            event = self._published_events.pop(0)
            
            new_correlation_id = str(uuid.uuid4())
            logger.info(
                f"Consumed event {event.event_type}",
                extra={"correlation_id": new_correlation_id}
            )
            return event
        return None

    def get_published_events(self) -> List[Event]:
        """Get list of published events (for testing)."""
        return list(self._published_events)


class IdempotencyTracker:
    """Track processed events to ensure exactly-once delivery."""

    def __init__(self, ttl_seconds: float = 3600.0):
        self.ttl_seconds = ttl_seconds
        self._processed: Dict[str, float] = {}

    def is_duplicate(self, event_id: str) -> bool:
        """Check if an event has already been processed."""
        for key in self._processed:
            if event_id in key:
                return True
        return False

    def mark_processed(self, event: Event):
        """Mark an event as processed."""
        key = f"{event.source_service}:{event.event_type}:{event.event_id}"
        self._processed[key] = time.time()

    def check_and_mark(self, event: Event) -> bool:
        """Atomically check if duplicate and mark as processed. Returns True if new."""
        key = f"{event.source_service}:{event.event_type}:{event.event_id}"
        if key in self._processed:
            return False
        self._processed[key] = time.time()
        return True

    def cleanup_expired(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, ts in self._processed.items() if now - ts > self.ttl_seconds]
        for k in expired:
            del self._processed[k]

    def get_processed_count(self) -> int:
        return len(self._processed)


class EventReplayManager:
    """Replay events from a stored log for recovery or reprocessing."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._replay_log: List[Event] = []
        self._replayed_ids: set = set()

    def store_for_replay(self, event: Event):
        """Store an event for potential replay."""
        self._replay_log.append(event)

    def replay_all(self, topic: str) -> int:
        """Replay all stored events to a topic."""
        count = 0
        for event in self._replay_log:
            replay_key = f"{event.event_id}:{time.time()}"
            if replay_key in self._replayed_ids:
                continue
            self._replayed_ids.add(replay_key)
            self.event_bus.publish(topic, event)
            count += 1
        return count

    def replay_since(self, topic: str, since_timestamp: str) -> int:
        """Replay events newer than a timestamp."""
        count = 0
        for event in self._replay_log:
            if event.timestamp >= since_timestamp:
                self.event_bus.publish(topic, event)
                count += 1
        return count

    def get_replay_log_size(self) -> int:
        return len(self._replay_log)


class DeadLetterQueue:
    """Store events that failed processing for later retry."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self._queue: List[Dict[str, Any]] = []
        self._retry_counts: Dict[str, int] = {}

    def push(self, event: Event, error: str):
        """Push a failed event to the dead letter queue."""
        self._queue.append({
            "event": event,
            "error": error,
            "pushed_at": time.time(),
        })
        self._retry_counts[event.event_id] = self._retry_counts.get(event.event_id, 0) + 1

    def pop(self) -> Optional[Dict[str, Any]]:
        """Pop the oldest event from the queue."""
        if not self._queue:
            return None
        return self._queue.pop(0)

    def can_retry(self, event_id: str) -> bool:
        """Check if an event can be retried."""
        count = self._retry_counts.get(event_id, 0)
        return count < self.max_retries

    def get_size(self) -> int:
        return len(self._queue)

    def get_retry_count(self, event_id: str) -> int:
        return self._retry_counts.get(event_id, 0)
