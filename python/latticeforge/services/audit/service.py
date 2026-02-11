from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

SERVICE_NAME = "audit"
SERVICE_ROLE = "immutable event trail"


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    trace_id: str
    mission_id: str
    service: str
    kind: str
    payload: Mapping[str, Any]
    timestamp: datetime


class AuditLedger:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._seen_ids: set[str] = set()
        self._duplicates = 0

    def append(self, event: AuditEvent) -> bool:
        duplicate = event.event_id in self._seen_ids
        if duplicate:
            self._duplicates += 1
        self._seen_ids.add(event.event_id)

        
        self._events.append(event)
        return not duplicate

    def by_trace(self, trace_id: str) -> list[AuditEvent]:
        out = [event for event in self._events if event.trace_id == trace_id]
        return sorted(out, key=lambda event: event.timestamp)

    def recent(self, limit: int = 50) -> list[AuditEvent]:
        return list(sorted(self._events, key=lambda event: event.timestamp, reverse=True)[:limit])

    def mission_gap_seconds(self, mission_id: str) -> int:
        mission_events = [event for event in self._events if event.mission_id == mission_id]
        if len(mission_events) <= 1:
            return 0
        ordered = sorted(mission_events, key=lambda event: event.timestamp)
        max_gap = 0
        for left, right in zip(ordered, ordered[1:]):
            gap = int((right.timestamp - left.timestamp).total_seconds())
            if gap > max_gap:
                max_gap = gap
        return max_gap

    def duplicate_count(self) -> int:
        return self._duplicates

    def export_trace(self, trace_id: str) -> list[dict[str, Any]]:
        exported: list[dict[str, Any]] = []
        for event in self.by_trace(trace_id):
            exported.append(
                {
                    "event_id": event.event_id,
                    "trace_id": event.trace_id,
                    "mission_id": event.mission_id,
                    "service": event.service,
                    "kind": event.kind,
                    "timestamp": event.timestamp.isoformat(),
                }
            )
        return exported


class EventPipeline:
    STAGES = ("received", "validated", "enriched", "persisted", "acknowledged")

    def __init__(self) -> None:
        self._events: dict[str, dict[str, object]] = {}

    def receive(self, event_id: str, payload: dict) -> None:
        self._events[event_id] = {
            "stage": "received",
            "payload": dict(payload),
            "retries": 0,
            "enrichment": {},
        }

    def validate(self, event_id: str) -> bool:
        ev = self._events.get(event_id)
        if not ev or ev["stage"] != "received":
            return False
        payload = ev["payload"]
        if not payload.get("trace_id") or not payload.get("service"):
            ev["retries"] = int(ev["retries"]) + 1
            return False
        ev["stage"] = "validated"
        return True

    def enrich(self, event_id: str, metadata: dict) -> bool:
        ev = self._events.get(event_id)
        if not ev or ev["stage"] != "validated":
            return False
        ev["enrichment"] = dict(metadata)
        ev["stage"] = "enriched"
        return True

    def persist(self, event_id: str) -> bool:
        ev = self._events.get(event_id)
        if not ev or ev["stage"] != "enriched":
            return False
        if not ev["enrichment"]:
            return False
        ev["stage"] = "persisted"
        return True

    def acknowledge(self, event_id: str) -> bool:
        ev = self._events.get(event_id)
        if not ev or ev["stage"] != "persisted":
            return False
        ev["stage"] = "acknowledged"
        return True

    def retry(self, event_id: str, fixed_payload: dict) -> bool:
        ev = self._events.get(event_id)
        if not ev:
            return False
        if ev["stage"] == "acknowledged":
            return False
        ev["stage"] = "received"
        ev["payload"] = dict(fixed_payload)
        ev["enrichment"] = ev.get("enrichment") or {}
        return True

    def get_stage(self, event_id: str) -> str:
        ev = self._events.get(event_id)
        return str(ev["stage"]) if ev else "unknown"

    def get_enrichment(self, event_id: str) -> dict:
        ev = self._events.get(event_id)
        return dict(ev.get("enrichment", {})) if ev else {}
