"""
HeliosOps Policy Engine
=======================

Escalation and compliance policy evaluation.  Implements a state machine for
operational modes (normal -> watch -> restricted -> halted) and SLA compliance
checking for emergency response targets.
"""
from __future__ import annotations

import copy
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .models import Incident, IncidentStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Operational mode state machine
# ---------------------------------------------------------------------------

ORDER = ["normal", "watch", "restricted", "halted"]

TRANSITION_THRESHOLDS: Dict[str, int] = {
    "normal": 3,       # 3+ failure bursts -> escalate to watch
    "watch": 2,        # 2+ failure bursts -> escalate to restricted
    "restricted": 1,   # 1+ failure burst  -> escalate to halted
    "halted": 0,       # already at maximum
}


def next_policy(current: str, failure_burst: int) -> str:
    """Advance the operational policy state based on failure burst count.

    Parameters
    ----------
    current : str
        Current state: one of 'normal', 'watch', 'restricted', 'halted'.
    failure_burst : int
        Number of consecutive failures observed.

    Returns
    -------
    str
        The next state.  May be the same state if failures are below threshold.
    """
    idx = ORDER.index(current) if current in ORDER else 0

    threshold = TRANSITION_THRESHOLDS.get(current, 1)
    if failure_burst >= threshold and idx < len(ORDER) - 1:
        return ORDER[idx + 1]

    # Allow recovery: no failures at all -> step down
    if failure_burst == 0 and idx > 0:
        return ORDER[idx - 1]

    return ORDER[idx]


def can_recover(current: str) -> bool:
    """Whether the system can recover (step down) from this state."""
    return current != "normal"


# ---------------------------------------------------------------------------
# SLA compliance
# ---------------------------------------------------------------------------

DEFAULT_SLA_CONFIG: Dict[int, int] = {
    5: 5,     # severity 5 -> 5 min SLA
    4: 15,    # severity 4 -> 15 min SLA
    3: 30,    # severity 3 -> 30 min SLA
    2: 60,    # severity 2 -> 60 min SLA
    1: 120,   # severity 1 -> 120 min SLA
}


def check_sla_compliance(
    incident: Incident,
    sla_config: Optional[Dict[int, int]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Check whether an incident is within its SLA window.


    Returns
    -------
    dict
        Keys: 'within_sla' (bool), 'remaining_minutes' (float),
              'sla_minutes' (int), 'elapsed_minutes' (float).
    """
    config = sla_config or DEFAULT_SLA_CONFIG
    now = now or datetime.now(timezone.utc)
    sla_minutes = config.get(incident.severity, 60)

    start_time = incident.created_at
    elapsed = (now - start_time).total_seconds() / 60.0
    remaining = sla_minutes - elapsed

    return {
        "within_sla": remaining > 0,
        "remaining_minutes": round(remaining, 2),
        "sla_minutes": sla_minutes,
        "elapsed_minutes": round(elapsed, 2),
    }


def find_sla_breaches(
    incidents: List[Incident],
    sla_config: Optional[Dict[int, int]] = None,
    now: Optional[datetime] = None,
) -> List[Incident]:
    """Return incidents that have breached their SLA."""
    breaches: List[Incident] = []
    for incident in incidents:
        if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
            continue
        result = check_sla_compliance(incident, sla_config, now)
        if not result["within_sla"]:
            breaches.append(incident)
    return breaches


# ---------------------------------------------------------------------------
# Escalation engine
# ---------------------------------------------------------------------------

ESCALATION_THRESHOLDS: Dict[int, int] = {
    5: 3,    # severity 5 -> escalate after 3 minutes
    4: 10,   # severity 4 -> escalate after 10 minutes
    3: 20,   # severity 3 -> escalate after 20 minutes
    2: 45,   # severity 2 -> escalate after 45 minutes
    1: 90,   # severity 1 -> escalate after 90 minutes
}


def evaluate_escalation(
    incident: Incident,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Determine whether an incident needs escalation.


    Returns
    -------
    dict
        Keys: 'should_escalate' (bool), 'minutes_overdue' (float),
              'threshold_minutes' (int).
    """
    now = now or datetime.now(timezone.utc)
    threshold_minutes = ESCALATION_THRESHOLDS.get(incident.severity, 30)

    elapsed_minutes = (now - incident.created_at).total_seconds() / 60.0

    should_escalate = elapsed_minutes > threshold_minutes
    minutes_overdue = max(0.0, elapsed_minutes - threshold_minutes)

    return {
        "should_escalate": should_escalate,
        "minutes_overdue": round(minutes_overdue, 2),
        "threshold_minutes": threshold_minutes,
    }


def bulk_evaluate_escalation(
    incidents: List[Incident],
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Evaluate escalation for a batch of incidents.

    Returns only incidents that require escalation.
    """
    results: List[Dict[str, Any]] = []
    for incident in incidents:
        if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
            continue
        eval_result = evaluate_escalation(incident, now)
        if eval_result["should_escalate"]:
            results.append({
                "incident_id": str(incident.id),
                "severity": incident.severity,
                **eval_result,
            })
    return results


# ---------------------------------------------------------------------------
# Consensus / voting for multi-node agreement
# ---------------------------------------------------------------------------

def check_consensus(
    votes: Dict[str, bool],
    nodes: List[str],
) -> bool:
    """Determine if a quorum of nodes agree (voted True).

    Parameters
    ----------
    votes : dict
        Mapping of node_id -> True (agree) or False (disagree).
    nodes : list of str
        All known node IDs in the cluster.

    Returns
    -------
    bool
        True if consensus is reached.
    """
    yes_count = sum(1 for node_id in nodes if votes.get(node_id, False))

    
    return yes_count >= len(nodes) / 2


# ---------------------------------------------------------------------------
# Event projection (read model)
# ---------------------------------------------------------------------------

class EventProjection:
    """Cached read model built from an event stream."""

    def __init__(self) -> None:
        self._snapshot: Optional[Dict[str, Any]] = None
        self._snapshot_time: Optional[float] = None
        self._events: List[Dict[str, Any]] = []

    def append_event(self, event: Dict[str, Any]) -> None:
        """Append an event to the stream."""
        event["_seq"] = len(self._events)
        event["_ts"] = time.time()
        self._events.append(event)

    def _build_snapshot(self) -> Dict[str, Any]:
        """Rebuild the read model from the full event stream."""
        projection: Dict[str, Any] = {}
        for event in self._events:
            event_type = event.get("type", "")
            entity_id = event.get("entity_id", "")
            if event_type == "created":
                projection[entity_id] = event.get("data", {})
            elif event_type == "updated" and entity_id in projection:
                projection[entity_id] = event.get("data", {})
            elif event_type == "deleted":
                projection.pop(entity_id, None)
        return projection

    def get_projection(self) -> Dict[str, Any]:
        """Return the current read model."""
        if self._snapshot is not None:
            return self._snapshot

        self._snapshot = self._build_snapshot()
        self._snapshot_time = time.time()
        return self._snapshot

    def refresh(self) -> Dict[str, Any]:
        """Force-rebuild the projection from the event stream."""
        self._snapshot = self._build_snapshot()
        self._snapshot_time = time.time()
        return self._snapshot

