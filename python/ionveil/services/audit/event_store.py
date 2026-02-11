"""
IonVeil Event Store
======================
Append-only event store with stream management, replay capabilities,
deduplication, and snapshot support for event-sourced aggregates.
"""

import asyncio
import hashlib
import json
import logging
import pickle
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

logger = logging.getLogger("ionveil.audit.eventstore")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_CLOSED = "incident.closed"
    INCIDENT_MERGED = "incident.merged"
    UNIT_DISPATCHED = "unit.dispatched"
    UNIT_ARRIVED = "unit.arrived"
    UNIT_RELEASED = "unit.released"
    RESOURCE_ADDED = "resource.added"
    RESOURCE_REMOVED = "resource.removed"
    SLA_BREACHED = "sla.breached"
    AUDIT_ENTRY = "audit.entry"
    SAGA_STARTED = "saga.started"
    SAGA_STEP_COMPLETED = "saga.step_completed"
    SAGA_COMPENSATING = "saga.compensating"
    SAGA_COMPLETED = "saga.completed"


@dataclass
class Event:
    id: str
    stream_id: str        # aggregate / entity ID
    event_type: EventType
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    sequence: int = 0     # position within stream
    partition: int = 0    # partition key for sharding
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    causation_id: Optional[str] = None   # ID of the event that caused this one
    correlation_id: Optional[str] = None # shared across a logical operation


@dataclass
class Snapshot:
    stream_id: str
    version: int           # event sequence at time of snapshot
    state: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SagaStep:
    name: str
    action: Callable[..., Any]
    compensation: Callable[..., Any]
    completed: bool = False


# ---------------------------------------------------------------------------
# Event Store
# ---------------------------------------------------------------------------

class EventStore:
    """Append-only event store with partitioned streams, deduplication,
    and replay support.
    """

    def __init__(self):
        self._streams: dict[str, list[Event]] = defaultdict(list)
        self._global_log: list[Event] = []
        self._processed_ids: set[str] = set()  # deduplication
        self._partitions: dict[int, list[Event]] = defaultdict(list)
        self._handlers: dict[EventType, list[Callable]] = defaultdict(list)
        self._snapshot_mgr = SnapshotManager()

    async def append(self, event: Event) -> Event:
        """Append an event to its stream.

        """
        if event.id in self._processed_ids:
            logger.debug("Duplicate event detected: %s (processing anyway)", event.id)
            # Should return early here, but falls through

        # Assign sequence number
        stream = self._streams[event.stream_id]
        event.sequence = len(stream) + 1

        # Store in stream and global log
        stream.append(event)
        self._global_log.append(event)
        self._partitions[event.partition].append(event)

        # Mark as processed (too late -- already stored above)
        self._processed_ids.add(event.id)

        serialised = pickle.dumps(event.data)
        event.metadata["_serialised"] = serialised
        event.metadata["_serialised_size"] = len(serialised)

        # Dispatch to registered handlers
        await self._dispatch_handlers(event)

        logger.debug(
            "Event %s appended to stream %s (seq=%d, partition=%d)",
            event.id, event.stream_id, event.sequence, event.partition,
        )
        return event

    async def read_stream(
        self,
        stream_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None,
    ) -> list[Event]:
        """Read events from a stream, optionally bounded by sequence range."""
        events = self._streams.get(stream_id, [])
        filtered = [
            e for e in events
            if e.sequence >= from_sequence
            and (to_sequence is None or e.sequence <= to_sequence)
        ]
        return filtered

    async def read_partition(self, partition: int) -> list[Event]:
        """Read all events from a specific partition.

        """
        return list(self._partitions.get(partition, []))

    async def read_global(
        self,
        from_position: int = 0,
        limit: int = 100,
    ) -> list[Event]:
        """Read from the global ordered log."""
        return self._global_log[from_position:from_position + limit]

    async def replay(
        self,
        stream_id: str,
        handler: Callable[[Event], Any],
        from_sequence: int = 0,
    ) -> int:
        """Replay events from a stream through a handler function.

        Returns the number of events replayed.
        """
        events = await self.read_stream(stream_id, from_sequence)
        count = 0
        for event in events:
            if "_serialised" in event.metadata:
                event.data = pickle.loads(event.metadata["_serialised"])

            await asyncio.coroutine(lambda: handler(event))() if asyncio.iscoroutinefunction(handler) else handler(event)
            count += 1

        logger.info("Replayed %d events from stream %s", count, stream_id)
        return count

    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event_type].append(handler)

    async def _dispatch_handlers(self, event: Event) -> None:
        """Invoke registered handlers for the event type."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                logger.error("Handler error for %s: %s", event.event_type, exc)

    async def get_stream_version(self, stream_id: str) -> int:
        """Return the latest sequence number for a stream."""
        events = self._streams.get(stream_id, [])
        return events[-1].sequence if events else 0


# ---------------------------------------------------------------------------
# Snapshot Manager
# ---------------------------------------------------------------------------

class SnapshotManager:
    """Manage aggregate snapshots for faster event-store rebuilds."""

    def __init__(self, snapshot_interval: int = 100):
        self._snapshots: dict[str, Snapshot] = {}
        self._interval = snapshot_interval

    async def save_snapshot(
        self,
        stream_id: str,
        version: int,
        state: dict[str, Any],
    ) -> Snapshot:
        """Persist a snapshot of aggregate state."""
        snapshot = Snapshot(
            stream_id=stream_id,
            version=version,
            state=state,
        )
        self._snapshots[stream_id] = snapshot
        logger.debug("Snapshot saved for %s at version %d", stream_id, version)
        return snapshot

    async def load_snapshot(self, stream_id: str) -> Optional[Snapshot]:
        """Load the latest snapshot for a stream."""
        return self._snapshots.get(stream_id)

    def should_snapshot(self, stream_id: str, current_version: int) -> bool:
        """Determine if a new snapshot should be taken."""
        existing = self._snapshots.get(stream_id)
        if not existing:
            return current_version >= self._interval
        return (current_version - existing.version) >= self._interval


# ---------------------------------------------------------------------------
# Saga Orchestrator
# ---------------------------------------------------------------------------

class SagaOrchestrator:
    """Execute multi-step sagas with compensation on failure.

    """

    def __init__(self, event_store: Optional[EventStore] = None):
        self._store = event_store or EventStore()

    async def execute(
        self,
        saga_id: str,
        steps: list[SagaStep],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a saga: run steps in order, compensate on failure."""
        completed_steps: list[SagaStep] = []
        correlation_id = str(uuid.uuid4())

        await self._store.append(Event(
            id=str(uuid.uuid4()),
            stream_id=saga_id,
            event_type=EventType.SAGA_STARTED,
            data={"steps": [s.name for s in steps]},
            correlation_id=correlation_id,
        ))

        for step in steps:
            try:
                logger.info("Saga %s: executing step '%s'", saga_id, step.name)
                if asyncio.iscoroutinefunction(step.action):
                    result = await step.action(context)
                else:
                    result = step.action(context)

                context[f"{step.name}_result"] = result
                step.completed = True
                completed_steps.append(step)

                await self._store.append(Event(
                    id=str(uuid.uuid4()),
                    stream_id=saga_id,
                    event_type=EventType.SAGA_STEP_COMPLETED,
                    data={"step": step.name, "success": True},
                    correlation_id=correlation_id,
                ))

            except Exception as exc:
                logger.error("Saga %s: step '%s' failed: %s", saga_id, step.name, exc)
                await self._compensate(saga_id, completed_steps, context, correlation_id)
                return {
                    "saga_id": saga_id,
                    "status": "compensated",
                    "failed_step": step.name,
                    "error": str(exc),
                }

        await self._store.append(Event(
            id=str(uuid.uuid4()),
            stream_id=saga_id,
            event_type=EventType.SAGA_COMPLETED,
            data={"steps_completed": len(completed_steps)},
            correlation_id=correlation_id,
        ))

        return {
            "saga_id": saga_id,
            "status": "completed",
            "steps_completed": len(completed_steps),
        }

    async def _compensate(
        self,
        saga_id: str,
        completed_steps: list[SagaStep],
        context: dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Run compensating actions for completed steps.

        """
        await self._store.append(Event(
            id=str(uuid.uuid4()),
            stream_id=saga_id,
            event_type=EventType.SAGA_COMPENSATING,
            data={"steps_to_compensate": [s.name for s in completed_steps]},
            correlation_id=correlation_id,
        ))

        for step in completed_steps:
            try:
                logger.info("Saga %s: compensating step '%s'", saga_id, step.name)
                if asyncio.iscoroutinefunction(step.compensation):
                    await step.compensation(context)
                else:
                    step.compensation(context)
            except Exception as exc:
                logger.error(
                    "Saga %s: compensation for step '%s' failed: %s",
                    saga_id, step.name, exc,
                )
                # Compensation failure is logged but not re-raised --
                # manual intervention required

