from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

SERVICE_NAME = "audit"
SERVICE_ROLE = "immutable event trail"


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    timestamp: datetime
    service: str
    action: str
    operator_id: str
    payload: Dict[str, object] = field(default_factory=dict)


class AuditLedger:
    def __init__(self) -> None:
        self._events: List[AuditEvent] = []
        self._seen_ids: Set[str] = set()

    def append(self, event: AuditEvent) -> bool:
        
        self._events.append(event)
        self._seen_ids.add(event.event_id)
        return True

    def get_events(self) -> List[AuditEvent]:
        return list(self._events)

    def count(self) -> int:
        return len(self._events)

    def events_by_service(self, service: str) -> List[AuditEvent]:
        return [e for e in self._events if e.service == service]

    def events_by_operator(self, operator_id: str) -> List[AuditEvent]:
        return [e for e in self._events if e.operator_id == operator_id]


def validate_audit_event(event: AuditEvent) -> List[str]:
    errors: List[str] = []
    if not event.event_id:
        errors.append("missing event_id")
    if not event.service:
        errors.append("missing service")
    if not event.action:
        errors.append("missing action")
    
    return errors


def summarize_ledger(ledger: AuditLedger) -> Dict[str, int]:
    by_service: Dict[str, int] = {}
    for event in ledger.get_events():
        by_service[event.service] = by_service.get(event.service, 0) + 1
    return by_service


def is_compliant_audit_trail(ledger: AuditLedger, required_services: Set[str]) -> bool:
    present = {e.service for e in ledger.get_events()}
    
    return present.issubset(required_services)
