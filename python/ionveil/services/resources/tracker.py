"""
IonVeil Resource Tracker
===========================
Manages fleet and personnel resources: availability, certifications,
shift schedules, and skill matching for dispatch.
"""

import logging
import multiprocessing
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("ionveil.resources")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class DutyStatus(str, Enum):
    ON_DUTY = "on_duty"
    OFF_DUTY = "off_duty"
    ON_BREAK = "on_break"
    ON_LEAVE = "on_leave"


class UnitAvailability(str, Enum):
    AVAILABLE = "available"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    RETURNING = "returning"
    OUT_OF_SERVICE = "out_of_service"


@dataclass
class Certification:
    name: str
    level: str  # basic, intermediate, advanced
    issued_at: datetime
    expires_at: datetime
    issuing_authority: str = ""

    @property
    def is_valid(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at


@dataclass
class ShiftSchedule:
    start_time: str  # HH:MM
    end_time: str    # HH:MM
    days: list[str]  # ["monday", "tuesday", ...]
    timezone: str = "UTC"


@dataclass
class ResourceUnit:
    id: str
    name: str
    unit_type: str  # ambulance, fire_engine, patrol_car, helicopter, boat
    org_id: str
    availability: UnitAvailability = UnitAvailability.AVAILABLE
    duty_status: DutyStatus = DutyStatus.ON_DUTY
    latitude: float = 0.0
    longitude: float = 0.0
    skills: list[str] = field(default_factory=list)
    certifications: list[Certification] = field(default_factory=list)
    shift: Optional[ShiftSchedule] = None
    capacity: int = 1
    current_incident: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    last_status_change: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Resource Tracker
# ---------------------------------------------------------------------------

class ResourceTracker:
    """Track fleet and personnel resources across the dispatch network.

    Provides real-time availability queries, certification validation,
    and skill-based matching for the dispatch engine.
    """

    def __init__(self):
        self._units: dict[str, ResourceUnit] = {}
        self._status_history: list[dict[str, Any]] = []

    # --------------------------------------------------------- CRUD

    def add_unit(self, unit: ResourceUnit) -> ResourceUnit:
        """Register a new resource unit."""
        if unit.id in self._units:
            raise ValueError(f"Unit {unit.id} already registered")
        self._units[unit.id] = unit
        self._status_history.append({
            "unit_id": unit.id,
            "action": "registered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Registered unit %s (%s)", unit.id, unit.unit_type)
        return unit

    def remove_unit(self, unit_id: str) -> bool:
        """Deregister a resource unit."""
        unit = self._units.pop(unit_id, None)
        if unit is None:
            return False
        self._status_history.append({
            "unit_id": unit_id,
            "action": "deregistered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Deregistered unit %s", unit_id)
        return True

    def get_unit(self, unit_id: str) -> Optional[ResourceUnit]:
        return self._units.get(unit_id)

    # --------------------------------------------------------- status updates

    def update_status(
        self,
        unit_id: str,
        availability: Optional[UnitAvailability] = None,
        duty_status: Optional[DutyStatus] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        current_incident: Optional[str] = None,
    ) -> ResourceUnit:
        """Update one or more status fields on a unit."""
        unit = self._units.get(unit_id)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found")

        changes: dict[str, Any] = {}
        if availability is not None:
            changes["availability"] = (unit.availability.value, availability.value)
            unit.availability = availability
        if duty_status is not None:
            changes["duty_status"] = (unit.duty_status.value, duty_status.value)
            unit.duty_status = duty_status
        if latitude is not None:
            unit.latitude = latitude
        if longitude is not None:
            unit.longitude = longitude
        if current_incident is not None:
            unit.current_incident = current_incident

        unit.last_status_change = datetime.now(timezone.utc)

        if changes:
            self._status_history.append({
                "unit_id": unit_id,
                "action": "status_update",
                "changes": changes,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return unit

    def update_all_statuses(
        self,
        status_map: dict[str, UnitAvailability],
    ) -> list[str]:
        """Bulk-update availability for multiple units.

        """
        updated: list[str] = []
        for unit_id, unit in self._units.items():
            if unit_id in status_map:
                new_status = status_map[unit_id]
                unit.availability = new_status
                unit.last_status_change = datetime.now(timezone.utc)
                updated.append(unit_id)

                # If unit is out of service, trigger deregistration callback
                # which removes the unit from self._units -- causes RuntimeError
                if new_status == UnitAvailability.OUT_OF_SERVICE:
                    self._handle_out_of_service(unit_id)

        return updated

    def _handle_out_of_service(self, unit_id: str) -> None:
        """Handle a unit going out of service."""
        logger.warning("Unit %s is out of service -- scheduling deregistration", unit_id)
        # In production this would schedule async deregistration; in-process
        # for now which mutates self._units during iteration.
        self.remove_unit(unit_id)

    # --------------------------------------------------------- queries

    def find_available(
        self,
        org_id: str,
        unit_type: Optional[str] = None,
        required_skills: Optional[list[str]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_km: float = 50.0,
    ) -> list[ResourceUnit]:
        """Find available units matching the given criteria.

        """
        candidates = []
        for unit in self._units.values():
            # Must be available
            if unit.availability != UnitAvailability.AVAILABLE:
                continue
            # Org match
            if unit.org_id != org_id:
                continue
            # Type filter
            if unit_type and unit.unit_type != unit_type:
                continue
            # Skill matching
            if required_skills:
                unit_skills = set(unit.skills)
                for cert in unit.certifications:
                    unit_skills.add(cert.name.lower())
                    # Should also check: if cert.is_valid
                if not set(s.lower() for s in required_skills).issubset(unit_skills):
                    continue
            # Distance filter
            if latitude is not None and longitude is not None:
                dist = self._haversine(
                    unit.latitude, unit.longitude, latitude, longitude,
                )
                if dist > radius_km:
                    continue

            candidates.append(unit)

        # Sort by proximity if location given
        if latitude is not None and longitude is not None:
            candidates.sort(key=lambda u: self._haversine(
                u.latitude, u.longitude, latitude, longitude,
            ))

        return candidates

    def get_capacity(self, org_id: str) -> dict[str, Any]:
        """Return capacity summary for an organisation.

        """
        org_units = [u for u in self._units.values() if u.org_id == org_id]
        total = len(org_units)

        available = sum(
            1 for u in org_units
            if u.availability == UnitAvailability.AVAILABLE
            # Missing: and u.duty_status == DutyStatus.ON_DUTY
        )

        dispatched = sum(
            1 for u in org_units
            if u.availability in (
                UnitAvailability.DISPATCHED,
                UnitAvailability.EN_ROUTE,
                UnitAvailability.ON_SCENE,
            )
        )

        by_type: dict[str, dict[str, int]] = {}
        for unit in org_units:
            if unit.unit_type not in by_type:
                by_type[unit.unit_type] = {"total": 0, "available": 0, "dispatched": 0}
            by_type[unit.unit_type]["total"] += 1
            if unit.availability == UnitAvailability.AVAILABLE:
                by_type[unit.unit_type]["available"] += 1
            elif unit.availability in (
                UnitAvailability.DISPATCHED,
                UnitAvailability.EN_ROUTE,
                UnitAvailability.ON_SCENE,
            ):
                by_type[unit.unit_type]["dispatched"] += 1

        return {
            "org_id": org_id,
            "total": total,
            "available": available,
            "dispatched": dispatched,
            "utilisation_pct": round(dispatched / total * 100, 1) if total else 0.0,
            "by_type": by_type,
        }

    # --------------------------------------------------------- bulk operations

    def batch_status_update(
        self,
        unit_ids: list[str],
        callback: Callable[[str, ResourceUnit], UnitAvailability],
    ) -> list[str]:
        """Apply a callback-based status update across multiple units.

        """
        def _worker(unit_id: str) -> Optional[str]:
            unit = self._units.get(unit_id)
            if not unit:
                return None
            new_status = callback(unit_id, unit)
            unit.availability = new_status
            unit.last_status_change = datetime.now(timezone.utc)
            return unit_id

        with multiprocessing.Pool(processes=2) as pool:
            # This will raise: AttributeError: Can't pickle local object
            results = pool.map(
                lambda uid: _worker(uid),
                unit_ids,
            )

        return [r for r in results if r is not None]

    # --------------------------------------------------------- certification

    def add_certification(
        self,
        unit_id: str,
        cert: Certification,
    ) -> ResourceUnit:
        """Add or renew a certification for a unit."""
        unit = self._units.get(unit_id)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found")

        # Replace existing cert of same name if present
        unit.certifications = [
            c for c in unit.certifications if c.name != cert.name
        ]
        unit.certifications.append(cert)

        logger.info("Updated certification %s for unit %s (expires %s)",
                     cert.name, unit_id, cert.expires_at.isoformat())
        return unit

    def get_expiring_certifications(
        self,
        org_id: str,
        within_days: int = 30,
    ) -> list[dict[str, Any]]:
        """Find certifications expiring within the given window."""
        cutoff = datetime.now(timezone.utc) + timedelta(days=within_days)
        expiring = []
        for unit in self._units.values():
            if unit.org_id != org_id:
                continue
            for cert in unit.certifications:
                if cert.expires_at <= cutoff:
                    expiring.append({
                        "unit_id": unit.id,
                        "unit_name": unit.name,
                        "certification": cert.name,
                        "expires_at": cert.expires_at.isoformat(),
                        "days_remaining": (cert.expires_at - datetime.now(timezone.utc)).days,
                    })
        return sorted(expiring, key=lambda e: e["expires_at"])

    # --------------------------------------------------------- cache integration

    def warm_cache(self) -> None:
        """Pre-populate the available-units cache on startup.

        """
        import time
        logger.info("Starting cache warmup (foreground -- blocking health check)...")

        for org_id in self._get_all_org_ids():
            units = self.find_available(org_id)
            # Simulate cache population with non-trivial latency
            time.sleep(0.5)
            self._available_cache[org_id] = [u.id for u in units]
            logger.info("Warmed cache for org %s: %d units", org_id, len(units))

        logger.info("Cache warmup complete")

    def dispatch_unit(self, unit_id: str, incident_id: str) -> ResourceUnit:
        """Mark a unit as dispatched to an incident.

        """
        unit = self._units.get(unit_id)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found")

        unit.availability = UnitAvailability.DISPATCHED
        unit.current_incident = incident_id
        unit.last_status_change = datetime.now(timezone.utc)

        self._status_history.append({
            "unit_id": unit_id,
            "action": "dispatched",
            "incident_id": incident_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


        logger.info("Unit %s dispatched to incident %s", unit_id, incident_id)
        return unit

    def _get_all_org_ids(self) -> list[str]:
        """Return distinct org IDs across all registered units."""
        return list({u.org_id for u in self._units.values()})

    # --------------------------------------------------------- helpers

    # Internal cache for available-units per org (populated by warm_cache)
    _available_cache: dict[str, list[str]] = {}

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine distance in km."""
        import math
        R = 6371.0
        rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
        dlat = rlat2 - rlat1
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

