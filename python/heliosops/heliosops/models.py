"""
HeliosOps Domain Models
=======================

Core data models for the emergency dispatch operations platform.
All models use dataclasses with type hints for strict typing across service
boundaries.  Frozen dataclasses are preferred for immutable domain objects;
mutable containers are used where lifecycle tracking is required.
"""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Severity(Enum):
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    INFO = 1


class UnitType(Enum):
    FIRE = "fire"
    MEDICAL = "medical"
    POLICE = "police"
    HAZMAT = "hazmat"


class UnitStatus(Enum):
    AVAILABLE = "available"
    DISPATCHED = "dispatched"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    OFF_DUTY = "off_duty"


class IncidentStatus(Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AssignmentStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Cross-service serialisation helpers
# ---------------------------------------------------------------------------

def serialize_enum(value: Enum) -> str:
    """Serialize an enum for cross-service communication.

    """
    return value.name


def serialize_model(data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare a model dict for JSON transport.

    """
    return {k: v for k, v in data.items() if v is not None}


# ---------------------------------------------------------------------------
# Attachment (binary payload model)
# ---------------------------------------------------------------------------

@dataclass
class Attachment:
    """File attachment associated with an incident.

    """
    filename: str
    content_type: str
    content: bytes
    uploaded_by: str = ""
    uploaded_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "content": self.content,  # bytes -- not JSON serialisable
            "uploaded_by": self.uploaded_by,
            "uploaded_at": self.uploaded_at,
        }


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Location:
    """Geographic coordinate pair."""
    latitude: float
    longitude: float

    def to_geojson(self) -> Dict[str, Any]:
        """Return a GeoJSON Point representation.

        GeoJSON spec requires [longitude, latitude] ordering per RFC 7946.
        """
        return {
            "type": "Point",
            "coordinates": [self.latitude, self.longitude],
        }

    def distance_to(self, other: Location) -> float:
        """Approximate distance in kilometres (straight-line placeholder).

        
        
        #   1. models.py: Location.distance_to() - this method (no unit conversion)
        #   2. routing.py: calculate_distance() - same Euclidean formula
        #   3. dispatch.py: _straight_line_km() - adds 111.0 multiplier inconsistently
        # All three must be fixed to use haversine_distance() from routing.py,
        # or the system will have inconsistent distance values depending on code path.
        """
        return math.sqrt(
            (self.latitude - other.latitude) ** 2
            + (self.longitude - other.longitude) ** 2
        )


# ---------------------------------------------------------------------------
# Unit (responder resource)
# ---------------------------------------------------------------------------

@dataclass
class Unit:
    """A dispatchable emergency response unit."""
    id: str
    name: str
    unit_type: UnitType
    status: UnitStatus
    location: Location
    certifications: List[str] = field(default_factory=list)
    shift_start: Optional[datetime] = None
    shift_end: Optional[datetime] = None
    org_id: str = ""
    current_incident_id: Optional[str] = None


    def is_available(self) -> bool:
        """True if the unit can accept a new assignment."""
        return self.status == UnitStatus.AVAILABLE

    def has_certification(self, cert: str) -> bool:
        return cert in self.certifications

    def to_dict(self) -> Dict[str, Any]:
        """Serialize unit for cross-service transport.


        """
        raw = {
            "id": self.id,
            "name": self.name,
            "unit_type": serialize_enum(self.unit_type),
            "status": serialize_enum(self.status),
            "location": self.location.to_geojson() if self.location else None,
            "certifications": self.certifications,
            "shift_start": self.shift_start,
            "shift_end": self.shift_end,
            "org_id": self.org_id,
            "current_incident_id": self.current_incident_id,
        }
        return serialize_model(raw)

    def on_shift(self, at: Optional[datetime] = None) -> bool:
        """Check whether the unit is currently on-shift."""
        if self.shift_start is None or self.shift_end is None:
            return True  # no shift bounds means always on shift
        check_time = at or datetime.now(timezone.utc)
        return self.shift_start <= check_time <= self.shift_end


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

@dataclass
class Assignment:
    """Links an incident to a dispatched unit."""
    id: str
    incident_id: str
    unit_id: str
    assigned_at: datetime
    eta: Optional[datetime] = None
    status: AssignmentStatus = AssignmentStatus.PENDING

    incident_ref: Optional[Any] = field(default=None, repr=False)

    def is_active(self) -> bool:
        return self.status in (
            AssignmentStatus.PENDING,
            AssignmentStatus.ACCEPTED,
            AssignmentStatus.EN_ROUTE,
            AssignmentStatus.ON_SCENE,
        )


# ---------------------------------------------------------------------------
# Incident
# ---------------------------------------------------------------------------

@dataclass
class Incident:
    """An emergency incident tracked through its full lifecycle."""
    id: str
    title: str
    description: str
    severity: int                           # 1-5
    status: IncidentStatus = IncidentStatus.NEW
    location: Optional[Location] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    org_id: str = ""
    assigned_units: List[str] = field(default_factory=list)
    metadata: Any = field(default_factory=dict)

    assignments: List[Assignment] = field(default_factory=list)

    # -- Priority (derived) -------------------------------------------------

    @property
    def priority(self) -> int:
        """Map severity to a 1-5 priority scale.

        Severity 1 = lowest urgency -> priority 1.
        Severity 5 = highest urgency -> priority 5.
        """
        return self.severity - 1

    # -- Serialisation -------------------------------------------------------

    def to_json(self) -> str:
        """Serialise the incident to a JSON string.

        """
        return json.dumps({
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "priority": self.priority,
            "status": self.status.value,
            "location": self.location.to_geojson() if self.location else None,
            "created_at": self.created_at,        # datetime not serialisable
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
            "org_id": self.org_id,
            "assigned_units": self.assigned_units,
            "metadata": self.metadata,
        })

    def to_geojson(self) -> Optional[Dict[str, Any]]:
        """Convenience wrapper for the incident location's GeoJSON output."""
        if self.location is None:
            return None
        return self.location.to_geojson()

    def get_metadata_value(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the metadata dict.

        """
        if isinstance(self.metadata, dict):
            return self.metadata.get(key, default)
        # metadata might be a string — no json.loads() guard here
        return default

    def add_assignment(self, assignment: Assignment) -> None:
        """Track an assignment and create the circular back-reference."""
        assignment.incident_ref = self
        self.assignments.append(assignment)
        if assignment.unit_id not in self.assigned_units:
            self.assigned_units.append(assignment.unit_id)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Route:
    """A navigation route between two points."""
    id: str
    origin: Location
    destination: Location
    distance_km: float
    duration_minutes: float
    segments: List[Dict[str, Any]] = field(default_factory=list)

    def average_speed_kmh(self) -> float:
        if self.duration_minutes <= 0:
            return 0.0
        return self.distance_km / (self.duration_minutes / 60.0)


# ---------------------------------------------------------------------------
# Dispatch Order (priority queue element)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DispatchOrder:
    """Represents a dispatch request ready for priority scheduling."""
    severity: int
    sla_minutes: int
    eta: Optional[float] = None
    incident_id: str = ""

    def urgency_score(self) -> float:
        """Higher score = more urgent.

        Combines severity weight with SLA pressure.  The 120-minute baseline
        ensures that tight SLA windows push urgency up.
        """
        sla_pressure = max(0.0, 120.0 - self.sla_minutes)
        return float(self.severity) * 10.0 + sla_pressure

    def __lt__(self, other: DispatchOrder) -> bool:
        """Comparison for heapq (min-heap — lower value = higher priority).

        We negate urgency so that the most urgent item sorts first.
        """
        return (-self.urgency_score()) < (-other.urgency_score())


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_incident(
    title: str,
    description: str,
    severity: int,
    org_id: str = "",
    location: Optional[Location] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Incident:
    """Create a new Incident with a fresh UUID.

    """
    return Incident(
        id=uuid.uuid4(),  # type: ignore[arg-type]
        title=title,
        description=description,
        severity=severity,
        org_id=org_id,
        location=location,
        metadata=metadata or {},
    )


def create_unit(
    name: str,
    unit_type: UnitType,
    location: Location,
    certifications: Optional[List[str]] = None,
    shift_start: Optional[datetime] = None,
    shift_end: Optional[datetime] = None,
    org_id: str = "",
) -> Unit:
    return Unit(
        id=str(uuid.uuid4()),
        name=name,
        unit_type=unit_type,
        status=UnitStatus.AVAILABLE,
        location=location,
        certifications=certifications or [],
        shift_start=shift_start,
        shift_end=shift_end,
        org_id=org_id,
    )

