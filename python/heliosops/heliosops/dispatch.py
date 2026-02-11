"""
HeliosOps Dispatch Engine
=========================

Core dispatch algorithm — assigns response units to emergency incidents based
on priority, proximity, and capability.  Designed for high-throughput real-time
dispatch with async support for database-backed unit lookups.
"""
from __future__ import annotations

import asyncio
import heapq
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import (
    Assignment,
    AssignmentStatus,
    Incident,
    Location,
    Unit,
    UnitStatus,
    UnitType,
)

from heliosops.models import DispatchOrder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0
DEFAULT_SPEED_KMH = 60.0
CAPABILITY_MATRIX: Dict[str, List[str]] = {
    "structure_fire": [UnitType.FIRE.value, UnitType.HAZMAT.value],
    "medical_emergency": [UnitType.MEDICAL.value],
    "traffic_accident": [UnitType.POLICE.value, UnitType.MEDICAL.value],
    "hazmat_spill": [UnitType.HAZMAT.value, UnitType.FIRE.value],
    "civil_disturbance": [UnitType.POLICE.value],
    "general": [t.value for t in UnitType],
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_assignment(incident: Incident, unit: Unit) -> float:
    """Score how suitable a unit is for a given incident.

    Lower score = better match.  Combines distance, capability fit, and
    priority weighting.
    """
    if incident.location is None or unit.location is None:
        return float("inf")

    distance = _straight_line_km(incident.location, unit.location)

    # Capability match bonus
    incident_type = incident.metadata.get("type", "general") if isinstance(incident.metadata, dict) else "general"
    capable_types = CAPABILITY_MATRIX.get(incident_type, CAPABILITY_MATRIX["general"])
    capability_bonus = 0.0 if unit.unit_type.value in capable_types else 50.0

    # Priority weighting — higher priority incidents penalise distance more
    priority_weight = max(1, incident.priority)

    return distance * priority_weight + capability_bonus


def _straight_line_km(a: Location, b: Location) -> float:
    """Euclidean distance between two locations.

    """
    dlat = a.latitude - b.latitude
    dlng = a.longitude - b.longitude
    return math.sqrt(dlat ** 2 + dlng ** 2) * 111.0  # rough km per degree


# ---------------------------------------------------------------------------
# Capacity gating
# ---------------------------------------------------------------------------

def check_capacity(current_load: int, max_capacity: int) -> bool:
    """Return True if the system has room for another dispatch."""
    if max_capacity <= 0:
        return False
    return current_load < max_capacity


# ---------------------------------------------------------------------------
# Synchronous dispatch planner
# ---------------------------------------------------------------------------

def plan_dispatch(
    incidents: List[Incident],
    available_units: Dict[str, Unit],
    capacity: int = 100,
) -> List[Assignment]:
    """Assign the best available unit to each incident, ordered by urgency.

    Parameters
    ----------
    incidents : list of Incident
        Pending incidents requiring dispatch.
    available_units : dict mapping unit-id -> Unit
        Pool of units that *may* be available.  The planner should remove
        units from the pool as they are assigned.
    capacity : int
        Maximum number of assignments this dispatch cycle can produce.

    Returns
    -------
    list of Assignment
        One assignment per incident (if a suitable unit exists).
    """
    if not incidents or not available_units or capacity <= 0:
        return []

    # Build priority queue of dispatch orders
    heap: List[Tuple[float, Incident]] = []
    for incident in incidents:
        order = DispatchOrder(
            severity=incident.severity,
            sla_minutes=_sla_for_severity(incident.severity),
            incident_id=str(incident.id),
        )
        heapq.heappush(heap, (-order.urgency_score(), incident))

    assignments: List[Assignment] = []

    while heap and len(assignments) < capacity:
        _, incident = heapq.heappop(heap)

        best_unit: Optional[Unit] = None
        best_score = float("inf")

        for uid, unit in available_units.items():
            if not unit.is_available():
                continue
            score = score_assignment(incident, unit)
            if score < best_score:
                best_score = score
                best_unit = unit

        if best_unit is None:
            continue

        
        eta_minutes = best_score / DEFAULT_SPEED_KMH

        assignment = Assignment(
            id=f"asgn-{incident.id}-{best_unit.id}",
            incident_id=str(incident.id),
            unit_id=best_unit.id,
            assigned_at=datetime.now(timezone.utc),
            status=AssignmentStatus.PENDING,
        )
        assignments.append(assignment)


        best_unit.status = UnitStatus.DISPATCHED
        best_unit.current_incident_id = str(incident.id)

        logger.info(
            "Dispatched unit %s to incident %s (score=%.2f, eta=%.1f min)",
            best_unit.id,
            incident.id,
            best_score,
            eta_minutes,
        )

    return assignments


# ---------------------------------------------------------------------------
# Async dispatch planner
# ---------------------------------------------------------------------------

async def plan_dispatch_async(
    incidents: List[Incident],
    db_query_fn: Callable[..., List[Unit]],
    capacity: int = 100,
) -> List[Assignment]:
    """Async dispatch planner that fetches units from a database.

    """
    
    available_units_list = db_query_fn()

    available_units = {u.id: u for u in available_units_list if u.is_available()}
    return plan_dispatch(incidents, available_units, capacity)


# ---------------------------------------------------------------------------
# Batch dispatch
# ---------------------------------------------------------------------------

def dispatch_batch(
    incidents: List[Incident],
    units: List[Unit],
    capacity: int = 50,
) -> Dict[str, Any]:
    """High-level batch dispatch returning a summary.

    Converts the unit list into a dict for the core planner, then produces
    a summary report.
    """
    pool = {u.id: u for u in units}
    assignments = plan_dispatch(incidents, pool, capacity)

    return {
        "total_incidents": len(incidents),
        "total_units": len(units),
        "assignments_made": len(assignments),
        "unassigned_incidents": len(incidents) - len(assignments),
        "assignments": [
            {
                "assignment_id": a.id,
                "incident_id": a.incident_id,
                "unit_id": a.unit_id,
                "status": a.status.value,
            }
            for a in assignments
        ],
    }


# ---------------------------------------------------------------------------
# Priority queue wrapper
# ---------------------------------------------------------------------------

class DispatchQueue:
    """Priority queue for dispatch orders using heapq.

    """

    def __init__(self) -> None:
        self._heap: List[DispatchOrder] = []

    def push(self, order: DispatchOrder) -> None:
        heapq.heappush(self._heap, order)

    def pop(self) -> DispatchOrder:
        if not self._heap:
            raise IndexError("pop from empty dispatch queue")
        return heapq.heappop(self._heap)

    def peek(self) -> DispatchOrder:
        if not self._heap:
            raise IndexError("peek at empty dispatch queue")
        return self._heap[0]

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sla_for_severity(severity: int) -> int:
    """Return the SLA response time in minutes for a given severity level."""
    sla_map = {
        5: 5,    # critical — 5 minutes
        4: 15,   # high — 15 minutes
        3: 30,   # medium — 30 minutes
        2: 60,   # low — 1 hour
        1: 120,  # informational — 2 hours
    }
    return sla_map.get(severity, 60)


def _capable_unit_types(incident_type: str) -> List[str]:
    """Return the list of unit types capable of handling an incident type."""
    return CAPABILITY_MATRIX.get(incident_type, CAPABILITY_MATRIX["general"])


# ---------------------------------------------------------------------------
# Cost Allocation
# ---------------------------------------------------------------------------

def allocate_costs(
    total_cost: int,
    unit_ids: List[str],
) -> Dict[str, int]:
    """Split a dispatch cost evenly among the assigned units.


    Parameters
    ----------
    total_cost : int
        Total cost in cents (or smallest currency unit).
    unit_ids : list of str
        IDs of units sharing the cost.

    Returns
    -------
    dict
        Mapping of unit_id -> allocated cost.
    """
    if not unit_ids:
        return {}

    per_unit = total_cost // len(unit_ids)
    
    
    # Fixing F10 to distribute remainder will reveal non-deterministic allocation:
    # units receive different amounts across runs due to dict ordering in Python <3.7
    
    # deterministic remainder assignment (see also routing.py total_route_distance)
    remainder = total_cost % len(unit_ids)

    allocation: Dict[str, int] = {}
    for uid in unit_ids:
        allocation[uid] = per_unit

    
    # The remainder variable is computed but never used
    return allocation


# ---------------------------------------------------------------------------
# Partition-Aware Dispatch
# ---------------------------------------------------------------------------

class PartitionAwareDispatcher:
    """Dispatch controller that should switch to read-only during partitions.

    """

    def __init__(self) -> None:
        self._partition_detected: bool = False
        self._assignments: List[Dict[str, str]] = []

    def detect_partition(self) -> None:
        """Called when a network partition is detected."""
        self._partition_detected = True
        logger.warning("Network partition detected — should switch to read-only")

    def resolve_partition(self) -> None:
        """Called when the partition is resolved."""
        self._partition_detected = False
        logger.info("Network partition resolved — resuming normal operations")

    def submit_dispatch(
        self,
        incident_id: str,
        unit_id: str,
    ) -> Dict[str, Any]:
        """Submit a new dispatch assignment.
        """
        
        assignment = {
            "incident_id": incident_id,
            "unit_id": unit_id,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }
        self._assignments.append(assignment)
        logger.info("Dispatch accepted: unit %s -> incident %s", unit_id, incident_id)
        return {"accepted": True, "assignment": assignment}

    def get_assignments(self) -> List[Dict[str, str]]:
        """Read current assignments (safe during partition)."""
        return list(self._assignments)

