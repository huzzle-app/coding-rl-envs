"""
IonVeil Dispatch Engine
=========================
Core dispatch logic: assigns responder units to incidents based on
proximity, priority, skill requirements, and capacity constraints.
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("ionveil.dispatch")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class IncidentStatus(str, Enum):
    OPEN = "open"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    RESOLVED = "resolved"
    CLOSED = "closed"


class UnitStatus(str, Enum):
    AVAILABLE = "available"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    RETURNING = "returning"
    OFF_DUTY = "off_duty"


@dataclass
class Location:
    latitude: float
    longitude: float

    def distance_km(self, other: "Location") -> float:
        """Haversine distance in kilometres."""
        import math
        R = 6371.0
        lat1, lat2 = math.radians(self.latitude), math.radians(other.latitude)
        dlat = lat2 - lat1
        dlon = math.radians(other.longitude - self.longitude)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class Incident:
    id: str
    title: str
    description: str
    priority: int  # 1 (critical) - 5 (low)
    location: Location
    status: IncidentStatus = IncidentStatus.OPEN
    org_id: str = ""
    assigned_units: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1


@dataclass
class Unit:
    id: str
    name: str
    unit_type: str  # ambulance, fire_truck, patrol_car, helicopter
    status: UnitStatus = UnitStatus.AVAILABLE
    location: Optional[Location] = None
    skills: list[str] = field(default_factory=list)
    assigned_incident: Optional[str] = None
    capacity: int = 1


# ---------------------------------------------------------------------------
# In-memory persistence adapter for benchmark runtime.
# ---------------------------------------------------------------------------

class _DispatchDB:
    """In-memory storage that simulates an async database."""

    def __init__(self):
        self._incidents: dict[str, Incident] = {}
        self._units: dict[str, Unit] = {}
        self._assignments: list[dict[str, Any]] = []

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    async def save_incident(self, incident: Incident) -> None:
        self._incidents[incident.id] = incident

    async def get_unit(self, unit_id: str) -> Optional[Unit]:
        return self._units.get(unit_id)

    async def save_unit(self, unit: Unit) -> None:
        self._units[unit.id] = unit

    async def list_incidents(self, status: Optional[IncidentStatus] = None) -> list[Incident]:
        results = list(self._incidents.values())
        if status:
            results = [i for i in results if i.status == status]
        return results

    async def list_available_units(
        self, location: Optional[Location] = None, radius_km: float = 50.0,
    ) -> list[Unit]:
        units = [u for u in self._units.values() if u.status == UnitStatus.AVAILABLE]
        if location:
            units = [u for u in units if u.location and u.location.distance_km(location) <= radius_km]
        return units

    async def record_assignment(self, record: dict[str, Any]) -> None:
        self._assignments.append(record)


# ---------------------------------------------------------------------------
# Dispatch Engine
# ---------------------------------------------------------------------------

class DispatchEngine:
    """Orchestrates the assignment of responder units to incidents.

    Manages priority scoring, capacity checks, and status transitions.
    """

    def __init__(self, db: Optional[_DispatchDB] = None):
        self._db = db or _DispatchDB()
        self.counter: int = 0
        self._lock = asyncio.Lock()  # present but not used for counter

    # ------------------------------------------------------------------ core

    async def assign(
        self,
        incident_id: str,
        unit_ids: Optional[list[str]] = None,
        auto_select: bool = False,
        max_units: int = 3,
    ) -> dict[str, Any]:
        """Assign one or more units to an incident.

        If ``auto_select`` is True, automatically picks the closest
        available units.  Otherwise uses the supplied ``unit_ids``.
        """
        incident = await self._db.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
            raise ValueError(f"Cannot dispatch to a {incident.status.value} incident")

        if auto_select:
            available = await self._db.list_available_units(
                location=incident.location, radius_km=50.0,
            )
            available.sort(key=lambda u: u.location.distance_km(incident.location) if u.location else float("inf"))
            selected = available[:max_units]
        else:
            selected = []
            for uid in (unit_ids or []):
                unit = await self._db.get_unit(uid)
                if unit and unit.status == UnitStatus.AVAILABLE:
                    selected.append(unit)

        if not selected:
            logger.warning("No available units for incident %s", incident_id)
            return {"incident_id": incident_id, "assigned": [], "status": "no_units"}

        assigned_ids = []
        for unit in selected:
            unit.status = UnitStatus.DISPATCHED
            unit.assigned_incident = incident_id
            await self._db.save_unit(unit)
            assigned_ids.append(unit.id)

        incident.assigned_units.extend(assigned_ids)
        incident.status = IncidentStatus.DISPATCHED
        incident.updated_at = datetime.now(timezone.utc)
        await self._db.save_incident(incident)

        self.counter += 1

        await self._db.record_assignment({
            "id": str(uuid.uuid4()),
            "incident_id": incident_id,
            "unit_ids": assigned_ids,
            "dispatch_number": self.counter,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "Dispatched %d units to incident %s (dispatch #%d)",
            len(assigned_ids), incident_id, self.counter,
        )
        return {
            "incident_id": incident_id,
            "assigned": assigned_ids,
            "dispatch_number": self.counter,
            "status": "dispatched",
        }

    async def reassign(
        self,
        incident_id: str,
        from_unit_id: str,
        to_unit_id: str,
    ) -> dict[str, Any]:
        """Move a unit from one incident assignment to a different unit."""
        incident = await self._db.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        from_unit = await self._db.get_unit(from_unit_id)
        to_unit = await self._db.get_unit(to_unit_id)
        if not from_unit or not to_unit:
            raise ValueError("Invalid unit ID")
        if to_unit.status != UnitStatus.AVAILABLE:
            raise ValueError(f"Unit {to_unit_id} is not available")

        # Release old unit
        from_unit.status = UnitStatus.AVAILABLE
        from_unit.assigned_incident = None
        await self._db.save_unit(from_unit)

        # Assign new unit
        to_unit.status = UnitStatus.DISPATCHED
        to_unit.assigned_incident = incident_id
        await self._db.save_unit(to_unit)

        # Update incident roster
        if from_unit_id in incident.assigned_units:
            incident.assigned_units.remove(from_unit_id)
        incident.assigned_units.append(to_unit_id)
        incident.updated_at = datetime.now(timezone.utc)
        await self._db.save_incident(incident)

        logger.info("Reassigned %s -> %s for incident %s", from_unit_id, to_unit_id, incident_id)
        return {"incident_id": incident_id, "removed": from_unit_id, "added": to_unit_id}

    async def release(self, incident_id: str, unit_id: str) -> dict[str, Any]:
        """Release a unit from its current incident assignment."""
        incident = await self._db.get_incident(incident_id)
        unit = await self._db.get_unit(unit_id)
        if not incident or not unit:
            raise ValueError("Invalid incident or unit ID")

        unit.status = UnitStatus.AVAILABLE
        unit.assigned_incident = None
        await self._db.save_unit(unit)

        if unit_id in incident.assigned_units:
            incident.assigned_units.remove(unit_id)
        incident.updated_at = datetime.now(timezone.utc)
        await self._db.save_incident(incident)

        logger.info("Released unit %s from incident %s", unit_id, incident_id)
        return {"incident_id": incident_id, "released": unit_id}

    # ---------------------------------------------------------- queries

    async def list_active_incidents(self) -> list[dict[str, Any]]:
        """Return all active (non-closed) incidents with their assigned units.

        """
        incidents = await self._db.list_incidents()
        active = [i for i in incidents if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)]

        results = []
        for incident in active:
            assigned_units = []
            for uid in incident.assigned_units:
                unit = await self._db.get_unit(uid)
                if unit:
                    assigned_units.append({
                        "id": unit.id,
                        "name": unit.name,
                        "status": unit.status.value,
                        "type": unit.unit_type,
                    })
            results.append({
                "id": incident.id,
                "title": incident.title,
                "priority": incident.priority,
                "status": incident.status.value,
                "assigned_units": assigned_units,
                "created_at": incident.created_at.isoformat(),
            })

        return results

    async def update_incident(
        self,
        incident_id: str,
        updates: dict[str, Any],
    ) -> Incident:
        """Apply field-level updates to an incident.


        """
        incident = await self._db.get_incident(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        # Apply updates directly to the in-memory object
        for key, value in updates.items():
            if hasattr(incident, key):
                setattr(incident, key, value)

        incident.updated_at = datetime.now(timezone.utc)
        # No version increment or CAS check -- lost update possible
        await self._db.save_incident(incident)

        return incident

    # ---------------------------------------------------------- scoring

    def calculate_priority_score(self, incident: Incident, unit: Unit) -> float:
        """Score a unit's suitability for an incident (higher = better)."""
        score = 0.0

        # Priority weight (P1 = 100, P5 = 20)
        priority_weights = {1: 100, 2: 80, 3: 60, 4: 40, 5: 20}
        score += priority_weights.get(incident.priority, 30)

        # Distance penalty
        if unit.location and incident.location:
            dist = unit.location.distance_km(incident.location)
            score -= dist * 2  # -2 points per km

        # Skill bonus
        required_skills = self._skills_for_category(incident.description)
        matching = set(unit.skills) & set(required_skills)
        score += len(matching) * 15

        # Capacity bonus
        score += unit.capacity * 5

        return max(score, 0.0)

    @staticmethod
    def _skills_for_category(description: str) -> list[str]:
        """Derive required skills from the incident description."""
        skills = []
        desc_lower = description.lower()
        if any(w in desc_lower for w in ["fire", "blaze", "smoke"]):
            skills.extend(["firefighting", "hazmat"])
        if any(w in desc_lower for w in ["medical", "injury", "heart", "trauma"]):
            skills.extend(["emt", "paramedic"])
        if any(w in desc_lower for w in ["crime", "assault", "robbery", "armed"]):
            skills.extend(["law_enforcement", "negotiation"])
        if any(w in desc_lower for w in ["flood", "earthquake", "hurricane"]):
            skills.extend(["search_rescue", "heavy_equipment"])
        return skills

    # ---------------------------------------------------------- capacity

    async def get_capacity_summary(self) -> dict[str, Any]:
        """Return a summary of current dispatch capacity."""
        all_units = list(self._db._units.values())
        total = len(all_units)
        available = sum(1 for u in all_units if u.status == UnitStatus.AVAILABLE)
        dispatched = sum(1 for u in all_units if u.status == UnitStatus.DISPATCHED)
        on_scene = sum(1 for u in all_units if u.status == UnitStatus.ON_SCENE)

        by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "available": 0})
        for unit in all_units:
            by_type[unit.unit_type]["total"] += 1
            if unit.status == UnitStatus.AVAILABLE:
                by_type[unit.unit_type]["available"] += 1

        return {
            "total_units": total,
            "available": available,
            "dispatched": dispatched,
            "on_scene": on_scene,
            "utilisation_pct": round(((total - available) / total) * 100, 1) if total else 0,
            "by_type": dict(by_type),
        }
