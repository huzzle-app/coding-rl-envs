from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from latticeforge.models import BurnPlan, BurnWindow, IncidentTicket, OrbitalSnapshot
from latticeforge.orbit import allocate_burns, compute_delta_v, fuel_projection
from latticeforge.policy import compliance_tags, evaluate_risk

SERVICE_NAME = "orbit"
SERVICE_ROLE = "orbital state estimation"


@dataclass(frozen=True)
class OrbitExecutionPlan:
    required_delta_v: float
    burns: tuple[BurnPlan, ...]
    risk_score: float
    projected_fuel_kg: float
    compliance_tags: tuple[str, str]


def build_orbit_plan(
    snapshot: OrbitalSnapshot,
    windows: Iterable[BurnWindow],
    incidents: Iterable[IncidentTicket],
) -> OrbitExecutionPlan:
    window_list = tuple(windows)
    incident_list = tuple(incidents)

    distance = abs(snapshot.altitude_km - 540.0)
    required_delta_v = compute_delta_v(distance_km=distance, mass_kg=max(snapshot.fuel_kg, 1.0) * 4.8)
    burns = tuple(allocate_burns(window_list, required_delta_v))
    risk_score = evaluate_risk(snapshot, burns, incident_list)
    projected_fuel = fuel_projection(snapshot, burns)
    tags = compliance_tags(risk_score)
    return OrbitExecutionPlan(required_delta_v, burns, risk_score, projected_fuel, tags)


def burn_budget_headroom(plan: OrbitExecutionPlan) -> float:
    consumed = sum(burn.delta_v for burn in plan.burns)
    return round(max(plan.required_delta_v - consumed, 0.0), 6)


def hot_window_ids(plan: OrbitExecutionPlan, threshold: float = 0.7) -> list[str]:
    return [burn.window_id for burn in plan.burns if burn.delta_v >= threshold]
