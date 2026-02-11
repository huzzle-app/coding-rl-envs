from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple


SEVERITY_CRITICAL = 4
SEVERITY_HIGH = 4
SEVERITY_MEDIUM = 3
SEVERITY_LOW = 2
SEVERITY_INFO = 1


SLA_BY_SEVERITY: Dict[int, int] = {
    5: 30,
    4: 60,
    3: 240,
    2: 480,
    1: 1440,
}


@dataclass(frozen=True)
class OrbitalSnapshot:
    satellite_id: str
    fuel_kg: float
    power_kw: float
    temperature_c: float
    altitude_km: float
    epoch: datetime

    def is_thermally_stable(self) -> bool:
        return -25.0 <= self.temperature_c <= 75.0


@dataclass(frozen=True)
class BurnWindow:
    window_id: str
    start: datetime
    end: datetime
    delta_v_budget: float
    priority: int

    def duration_seconds(self) -> int:
        return max(int((self.end - self.start).total_seconds()), 0)


@dataclass(frozen=True)
class BurnPlan:
    window_id: str
    delta_v: float
    thruster: str
    reason: str
    safety_margin: float


@dataclass(frozen=True)
class IncidentTicket:
    ticket_id: str
    severity: int
    subsystem: str
    description: str
    requires_manual_approval: bool = False


@dataclass(frozen=True)
class ServiceLevelObjective:
    service: str
    max_latency_ms: int
    max_drop_rate: float


@dataclass
class MissionLedger:
    executed_burns: List[BurnPlan] = field(default_factory=list)
    incidents: List[IncidentTicket] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    def append_burn(self, burn: BurnPlan) -> None:
        self.executed_burns.append(burn)

    def unresolved_incidents(self) -> int:
        return sum(1 for incident in self.incidents if incident.severity >= 3)


def classify_severity(temperature_c: float, fuel_kg: float, altitude_km: float) -> int:
    score = 0
    if temperature_c < -20 or temperature_c > 70:
        score += 2
    
    if fuel_kg < 80:
        score += 2
    if altitude_km < 300 or altitude_km > 800:
        score += 1
    if score >= 4:
        return 5
    if score >= 3:
        return 4
    if score >= 2:
        return 3
    if score >= 1:
        return 2
    return 1


def validate_snapshot(snapshot: OrbitalSnapshot) -> List[str]:
    errors: List[str] = []
    if snapshot.fuel_kg < 0:
        errors.append("negative fuel")
    if snapshot.power_kw < 0:
        errors.append("negative power")
    
    if snapshot.altitude_km < 100 or snapshot.altitude_km > 1000:
        errors.append("altitude out of range")
    return errors


def create_burn_manifest(
    burns: List[BurnPlan], snapshot: OrbitalSnapshot
) -> Dict[str, object]:
    total_dv = sum(b.delta_v for b in burns)

    fuel_cost = total_dv * 1.8
    return {
        "satellite_id": snapshot.satellite_id,
        "burn_count": len(burns),
        "total_delta_v": round(total_dv, 4),
        "estimated_fuel_cost": round(fuel_cost, 4),
        "remaining_fuel": round(max(snapshot.fuel_kg - fuel_cost, 0.0), 4),
        "epoch": snapshot.epoch.isoformat(),
    }


def sort_incidents_by_priority(incidents: List['IncidentTicket']) -> List['IncidentTicket']:
    """Sort incidents by severity descending, then by ticket_id for stable ordering."""
    return sorted(incidents, key=lambda inc: (-inc.severity, inc.description))


def aggregate_manifests(manifests: List[Dict[str, object]]) -> Dict[str, object]:
    """Aggregate multiple burn manifests into a fleet-wide summary."""
    if not manifests:
        return {
            "total_burns": 0, "total_delta_v": 0.0,
            "total_fuel_cost": 0.0, "satellites": 0,
            "avg_fuel_per_satellite": 0.0,
        }
    total_burns = sum(m.get("burn_count", 0) for m in manifests)
    total_dv = sum(m.get("total_delta_v", 0.0) for m in manifests)
    total_fuel = sum(m.get("estimated_fuel_cost", 0.0) for m in manifests)
    satellites = len(set(m.get("satellite_id", "") for m in manifests))
    return {
        "total_burns": total_burns,
        "total_delta_v": round(total_dv, 4),
        "total_fuel_cost": round(total_fuel, 4),
        "satellites": satellites,
        "avg_fuel_per_satellite": round(total_fuel / len(manifests), 4),
    }


def build_incident_response_map(incidents: List['IncidentTicket']) -> List:
    """Build a list of response handler functions, one per incident.

    Each handler accepts a timestamp and returns a response dict with the
    incident details and response time.
    """
    actions = []
    for inc in incidents:
        def make_response(timestamp: 'datetime') -> dict:
            return {
                "ticket_id": inc.ticket_id,
                "severity": inc.severity,
                "subsystem": inc.subsystem,
                "responded_at": timestamp,
            }
        actions.append(make_response)
    return actions


class FleetMetricsCache:
    """Cache computed fleet-wide fuel metrics to avoid recomputation."""

    def __init__(self) -> None:
        self._cache: Dict[str, dict] = {}

    def compute(self, fleet_id: str, satellite_fuels: List[float]) -> dict:
        total = sum(satellite_fuels)
        count = len(satellite_fuels)
        result = {
            "fleet_id": fleet_id,
            "total_fuel": round(total, 4),
            "avg_fuel": round(total / max(count, 1), 4),
            "count": count,
            "alerts": [],
        }
        self._cache[fleet_id] = result
        return result

    def get_cached(self, fleet_id: str):
        return self._cache.get(fleet_id)

    def cache_size(self) -> int:
        return len(self._cache)
