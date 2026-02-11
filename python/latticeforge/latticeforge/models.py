from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


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
