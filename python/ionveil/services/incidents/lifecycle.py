"""
IonVeil Incident Lifecycle Management
========================================
Handles the full lifecycle of an incident: creation, classification,
state-machine transitions, merging, and closure.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("ionveil.incidents")


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class IncidentState(str, Enum):
    REPORTED = "reported"
    TRIAGED = "triaged"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    MERGED = "merged"


# Valid transitions (from -> set of allowed to)
VALID_TRANSITIONS: dict[IncidentState, set[IncidentState]] = {
    IncidentState.REPORTED:   {IncidentState.TRIAGED, IncidentState.CLOSED},
    IncidentState.TRIAGED:    {IncidentState.DISPATCHED, IncidentState.CLOSED},
    IncidentState.DISPATCHED: {IncidentState.EN_ROUTE, IncidentState.TRIAGED},
    IncidentState.EN_ROUTE:   {IncidentState.ON_SCENE, IncidentState.DISPATCHED},
    IncidentState.ON_SCENE:   {IncidentState.MITIGATED, IncidentState.RESOLVED},
    IncidentState.MITIGATED:  {IncidentState.RESOLVED, IncidentState.ON_SCENE},
    IncidentState.RESOLVED:   {IncidentState.CLOSED, IncidentState.ON_SCENE},
    IncidentState.CLOSED:     set(),  # terminal
    IncidentState.MERGED:     set(),  # terminal
}

PRIORITY_LABELS = {1: "critical", 2: "high", 3: "medium", 4: "low", 5: "informational"}

AUTO_TRIAGE_KEYWORDS: dict[str, int] = {
    "explosion": 1, "active shooter": 1, "mass casualty": 1,
    "structure fire": 2, "cardiac arrest": 2, "hazmat": 2,
    "traffic accident": 3, "medical emergency": 3,
    "noise complaint": 4, "parking violation": 5,
}


@dataclass
class IncidentRecord:
    id: str
    title: str
    description: str
    priority: int
    state: IncidentState
    org_id: str
    latitude: float
    longitude: float
    category: str = "general"
    assigned_units: list[str] = field(default_factory=list)
    audit_log: list[dict[str, Any]] = field(default_factory=list)
    merged_from: list[str] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    version: int = 1


# ---------------------------------------------------------------------------
# In-memory persistence adapter for benchmark runtime.
# ---------------------------------------------------------------------------

class _IncidentDB:
    """In-memory incident / audit store simulating PostgreSQL."""

    def __init__(self):
        self._incidents: dict[str, IncidentRecord] = {}
        self._audit_entries: list[dict[str, Any]] = []
        self._assignments: dict[str, list[str]] = {}  # incident_id -> unit_ids

    async def save(self, record: IncidentRecord) -> None:
        self._incidents[record.id] = record

    async def get(self, incident_id: str) -> Optional[IncidentRecord]:
        return self._incidents.get(incident_id)

    async def get_by_org(self, org_id: str) -> list[IncidentRecord]:
        return [r for r in self._incidents.values() if r.org_id == org_id]

    async def delete(self, incident_id: str) -> None:
        """Delete incident and associated data.

        """
        self._audit_entries = [
            e for e in self._audit_entries if e.get("incident_id") != incident_id
        ]
        self._assignments.pop(incident_id, None)
        self._incidents.pop(incident_id, None)

    async def add_audit(self, entry: dict[str, Any]) -> None:
        self._audit_entries.append(entry)

    async def get_audits_for_incident(self, incident_id: str) -> list[dict]:
        return [e for e in self._audit_entries if e.get("incident_id") == incident_id]

    async def update_assignments(self, incident_id: str, unit_ids: list[str]) -> None:
        self._assignments[incident_id] = unit_ids

    async def get_assignments(self, incident_id: str) -> list[str]:
        return self._assignments.get(incident_id, [])


# ---------------------------------------------------------------------------
# Incident Manager
# ---------------------------------------------------------------------------

class IncidentManager:
    """Full lifecycle management for IonVeil incidents."""

    def __init__(self, db: Optional[_IncidentDB] = None):
        self._db = db or _IncidentDB()

    # --------------------------------------------------------------- create

    async def create_incident(
        self,
        title: str,
        description: str,
        priority: int,
        org_id: str,
        latitude: float,
        longitude: float,
        category: str = "general",
        created_by: str = "system",
    ) -> IncidentRecord:
        """Create a new incident and apply auto-triage."""
        incident_id = str(uuid.uuid4())
        auto_priority = self._auto_triage_priority(description)
        effective_priority = min(priority, auto_priority) if auto_priority else priority

        record = IncidentRecord(
            id=incident_id,
            title=title,
            description=description,
            priority=effective_priority,
            state=IncidentState.REPORTED,
            org_id=org_id,
            latitude=latitude,
            longitude=longitude,
            category=category or self._classify(description),
            created_by=created_by,
        )
        await self._db.save(record)
        await self._record_audit(
            incident_id, "created", created_by,
            {"priority": effective_priority, "auto_triaged": auto_priority is not None},
        )

        logger.info("Created incident %s [P%d] for org %s", incident_id, effective_priority, org_id)
        return record

    # --------------------------------------------------------------- update

    async def update_incident(
        self,
        incident_id: str,
        updates: dict[str, Any],
        actor: str = "system",
    ) -> IncidentRecord:
        """Apply field-level updates to an incident."""
        record = await self._db.get(incident_id)
        if not record:
            raise ValueError(f"Incident {incident_id} not found")

        changed_fields = {}
        for key, value in updates.items():
            if key == "state":
                # Use the transition method for state changes
                continue
            if hasattr(record, key) and getattr(record, key) != value:
                changed_fields[key] = {"old": getattr(record, key), "new": value}
                setattr(record, key, value)

        if changed_fields:
            record.updated_at = datetime.now(timezone.utc)
            record.version += 1
            await self._db.save(record)
            await self._record_audit(incident_id, "updated", actor, changed_fields)

        return record

    # --------------------------------------------------------- transitions

    async def transition(
        self,
        incident_id: str,
        new_state: IncidentState,
        actor: str = "system",
        reason: str = "",
    ) -> IncidentRecord:
        """Transition an incident to a new state following the state machine."""
        record = await self._db.get(incident_id)
        if not record:
            raise ValueError(f"Incident {incident_id} not found")

        allowed = VALID_TRANSITIONS.get(record.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {record.state.value} -> {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        old_state = record.state
        record.state = new_state
        record.updated_at = datetime.now(timezone.utc)
        record.version += 1

        if new_state == IncidentState.CLOSED:
            record.closed_at = datetime.now(timezone.utc)

        await self._db.save(record)
        await self._record_audit(incident_id, "state_transition", actor, {
            "from": old_state.value,
            "to": new_state.value,
            "reason": reason,
        })

        logger.info("Incident %s: %s -> %s (by %s)", incident_id, old_state.value, new_state.value, actor)
        return record

    # --------------------------------------------------------------- merge

    async def merge_incidents(
        self,
        primary_id: str,
        secondary_id: str,
        actor: str = "system",
    ) -> IncidentRecord:
        """Merge secondary incident into primary.


        """
        primary = await self._db.get(primary_id)
        secondary = await self._db.get(secondary_id)
        if not primary or not secondary:
            raise ValueError("One or both incident IDs are invalid")
        if primary.org_id != secondary.org_id:
            raise ValueError("Cannot merge incidents across organisations")

        merged_units = list(primary.assigned_units)

        primary.assigned_units = merged_units
        primary.merged_from.append(secondary_id)
        primary.priority = min(primary.priority, secondary.priority)
        primary.description = (
            f"{primary.description}\n\n"
            f"--- Merged from {secondary_id} ---\n"
            f"{secondary.description}"
        )
        primary.updated_at = datetime.now(timezone.utc)
        primary.version += 1
        await self._db.save(primary)

        # Step 2: update assignments (separate "table")
        await self._db.update_assignments(primary_id, merged_units)

        # Step 3: mark secondary as merged
        secondary.state = IncidentState.MERGED
        secondary.assigned_units = []
        secondary.updated_at = datetime.now(timezone.utc)
        await self._db.save(secondary)

        await self._record_audit(primary_id, "merged", actor, {
            "secondary_id": secondary_id,
            "units_transferred": len(merged_units),
        })

        logger.info("Merged incident %s into %s", secondary_id, primary_id)
        return primary

    # --------------------------------------------------------------- close

    async def close_incident(
        self,
        incident_id: str,
        resolution: str = "",
        actor: str = "system",
    ) -> IncidentRecord:
        """Close an incident, releasing all assigned units."""
        record = await self._db.get(incident_id)
        if not record:
            raise ValueError(f"Incident {incident_id} not found")

        if record.state == IncidentState.CLOSED:
            return record  # idempotent

        # Must go through RESOLVED first unless already there
        if record.state not in (IncidentState.RESOLVED, IncidentState.REPORTED):
            raise ValueError(
                f"Cannot close incident in state {record.state.value}. "
                "Transition to RESOLVED first."
            )

        record.state = IncidentState.CLOSED
        record.closed_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)
        record.version += 1
        await self._db.save(record)

        await self._record_audit(incident_id, "closed", actor, {"resolution": resolution})
        logger.info("Closed incident %s", incident_id)
        return record

    # --------------------------------------------------------------- access

    async def get_incident(
        self,
        incident_id: str,
        requesting_org_id: Optional[str] = None,
    ) -> IncidentRecord:
        """Retrieve a single incident by ID.

        """
        record = await self._db.get(incident_id)
        if not record:
            raise ValueError(f"Incident {incident_id} not found")


        return record

    async def list_incidents(
        self,
        org_id: str,
        state_filter: Optional[IncidentState] = None,
    ) -> list[IncidentRecord]:
        """List incidents for an organisation with optional state filter."""
        records = await self._db.get_by_org(org_id)
        if state_filter:
            records = [r for r in records if r.state == state_filter]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    # --------------------------------------------------------------- helpers

    async def _record_audit(
        self,
        incident_id: str,
        action: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        """Append an immutable audit entry."""
        await self._db.add_audit({
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "action": action,
            "actor": actor,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @staticmethod
    def _auto_triage_priority(description: str) -> Optional[int]:
        """Derive priority from description keywords."""
        desc_lower = description.lower()
        best = None
        for keyword, priority in AUTO_TRIAGE_KEYWORDS.items():
            if keyword in desc_lower:
                if best is None or priority < best:
                    best = priority
        return best

    @staticmethod
    def _classify(description: str) -> str:
        """Auto-classify incident category from description."""
        desc_lower = description.lower()
        if any(w in desc_lower for w in ["fire", "blaze", "smoke", "arson"]):
            return "fire"
        if any(w in desc_lower for w in ["medical", "injury", "cardiac", "trauma", "overdose"]):
            return "medical"
        if any(w in desc_lower for w in ["crime", "assault", "robbery", "theft", "shooting"]):
            return "law_enforcement"
        if any(w in desc_lower for w in ["flood", "earthquake", "tornado", "hurricane", "storm"]):
            return "natural_disaster"
        if any(w in desc_lower for w in ["hazmat", "chemical", "spill", "radiation"]):
            return "hazmat"
        return "general"
