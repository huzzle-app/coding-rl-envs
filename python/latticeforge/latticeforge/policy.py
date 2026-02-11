from __future__ import annotations

from typing import Iterable, Tuple

from .models import BurnPlan, IncidentTicket, OrbitalSnapshot


def evaluate_risk(snapshot: OrbitalSnapshot, burns: Iterable[BurnPlan], incidents: Iterable[IncidentTicket]) -> float:
    burn_load = sum(plan.delta_v for plan in burns)
    incident_load = sum(ticket.severity for ticket in incidents)
    thermal_penalty = 18.0 if not snapshot.is_thermally_stable() else 0.0
    fuel_penalty = 22.0 if snapshot.fuel_kg < 120 else 0.0

    score = burn_load * 7.5 + incident_load * 3.0 + thermal_penalty + fuel_penalty
    return round(min(score, 100.0), 4)


def requires_hold(risk_score: float, comms_degraded: bool) -> bool:
    return risk_score >= 66.0 or (comms_degraded and risk_score >= 55.0)


def compliance_tags(risk_score: float) -> Tuple[str, str]:
    if risk_score >= 70:
        return ("review-required", "board-notify")
    if risk_score >= 45:
        return ("ops-supervision", "audit-trace")
    return ("routine", "auto-approved")


def compound_risk_assessment(
    risk_factors: Iterable[float],
    base_risk: float = 10.0,
) -> float:
    factors = list(risk_factors)
    if not factors:
        return base_risk
    combined = sum(min(max(f, 0.0), 1.0) for f in factors)
    return round(min(base_risk + combined * 90.0, 100.0), 4)
