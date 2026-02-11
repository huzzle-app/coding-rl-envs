"""
OmniCloud Event Publisher / Consumer Base
Terminal Bench v2 - Kafka-based event system for inter-service communication.

Contains bugs:
- L3: Topics not auto-created (Kafka auto.create.topics.enable is false)
- L14: Worker serializer uses pickle instead of JSON
- J1: Trace context lost across Kafka messages
"""
import json
import time
import uuid
import logging
import pickle
from typing import Any, Dict, Optional, Callable, List
from dataclasses import dataclass, field


import shared

logger = logging.getLogger(__name__)


@dataclass
class EventPublisher:
    """Publishes events to Kafka topics."""
    bootstrap_servers: str = "kafka:29092"
    
    serializer: str = "pickle"  # Should be "json"

    def serialize(self, event: Dict[str, Any]) -> bytes:
        """Serialize event for Kafka."""
        if self.serializer == "pickle":
            
            return pickle.dumps(event)
        return json.dumps(event).encode("utf-8")

    def deserialize(self, data: bytes) -> Dict[str, Any]:
        """Deserialize event from Kafka."""
        if self.serializer == "pickle":
            return pickle.loads(data)
        return json.loads(data.decode("utf-8"))

    def publish(
        self,
        topic: str,
        event_type: str,
        payload: Dict[str, Any],
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Publish an event to a Kafka topic.

        BUG J1: trace_id and correlation_id are not included in the message headers,
        so distributed tracing context is lost across Kafka boundaries.
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "payload": payload,
            "timestamp": time.time(),
            "tenant_id": tenant_id,
            
            # Missing: "trace_id": trace_id, "correlation_id": correlation_id
        }
        serialized = self.serialize(event)
        logger.info(f"Publishing {event_type} to {topic} ({len(serialized)} bytes)")
        return event


@dataclass
class EventConsumer:
    """Consumes events from Kafka topics."""
    bootstrap_servers: str = "kafka:29092"
    group_id: str = "default-group"
    topics: List[str] = field(default_factory=list)
    handlers: Dict[str, Callable] = field(default_factory=dict)
    serializer: str = "json"

    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for a specific event type."""
        self.handlers[event_type] = handler

    def process_event(self, raw_data: bytes) -> Optional[Dict[str, Any]]:
        """Process a raw event message."""
        try:
            if self.serializer == "json":
                event = json.loads(raw_data.decode("utf-8"))
            else:
                event = pickle.loads(raw_data)

            event_type = event.get("event_type")
            if event_type in self.handlers:
                self.handlers[event_type](event)
            return event
        except (json.JSONDecodeError, pickle.UnpicklingError) as e:
            logger.error(f"Failed to deserialize event: {e}")
            return None


@dataclass
class IdempotencyChecker:
    """Ensures event handlers are idempotent."""
    processed_ids: set = field(default_factory=set)
    max_size: int = 100000

    def is_duplicate(self, event_id: str) -> bool:
        """Check if event was already processed."""
        if event_id in self.processed_ids:
            return True
        if len(self.processed_ids) >= self.max_size:
            self.processed_ids.clear()
        self.processed_ids.add(event_id)
        return False


@dataclass
class EventReplayBuffer:
    """Buffer that stores events for replay during failure recovery.

    Maintains ordering guarantees and prevents event loss.
    """
    max_size: int = 10000
    _buffer: List[Dict[str, Any]] = field(default_factory=list)
    _sequence_number: int = 0

    def append(self, event: Dict[str, Any]) -> int:
        """Add an event to the replay buffer.

        Returns the sequence number assigned to the event.
        """
        self._sequence_number += 1
        event["_seq"] = self._sequence_number

        if len(self._buffer) >= self.max_size:
            # Drop oldest events when buffer is full
            self._buffer = self._buffer[len(self._buffer) // 2:]

        self._buffer.append(event)
        return self._sequence_number

    def replay_from(self, sequence_number: int) -> List[Dict[str, Any]]:
        """Replay events from a given sequence number."""
        return [e for e in self._buffer if e.get("_seq", 0) >= sequence_number]

    @property
    def size(self) -> int:
        return len(self._buffer)

    @property
    def oldest_sequence(self) -> int:
        if self._buffer:
            return self._buffer[0].get("_seq", 0)
        return 0


@dataclass
class OrderedEventProcessor:
    """Processes events in strict order, buffering out-of-order arrivals."""
    _expected_seq: int = 1
    _buffer: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    _processed: List[Dict[str, Any]] = field(default_factory=list)

    def process(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process an event, buffering if out of order.

        Returns list of events that were processed in order.
        """
        seq = event.get("_seq", 0)
        if seq == 0:
            # No sequence number, process immediately
            self._processed.append(event)
            return [event]

        self._buffer[seq] = event
        newly_processed = []

        # Process consecutive events from buffer
        while self._expected_seq in self._buffer:
            evt = self._buffer.pop(self._expected_seq)
            self._processed.append(evt)
            newly_processed.append(evt)
            self._expected_seq += 1

        return newly_processed

    @property
    def pending_count(self) -> int:
        return len(self._buffer)
