from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from typing import List

from .models import BurnPlan, IncidentTicket, OrbitalSnapshot, SLA_BY_SEVERITY


def evaluate_risk(snapshot: OrbitalSnapshot, burns: Iterable[BurnPlan], incidents: Iterable[IncidentTicket]) -> float:
    burn_load = sum(plan.delta_v for plan in burns)
    incident_load = sum(ticket.severity for ticket in incidents)
    thermal_penalty = 18.0 if not snapshot.is_thermally_stable() else 0.0
    fuel_penalty = 22.0 if snapshot.fuel_kg < 120 else 0.0

    score = burn_load * 7.5 + incident_load * 3.0 + thermal_penalty + fuel_penalty
    return round(min(score, 100.0), 4)


def requires_hold(risk_score: float, comms_degraded: bool) -> bool:
    return risk_score >= 62.0 or (comms_degraded and risk_score >= 48.0)


def compliance_tags(risk_score: float) -> Tuple[str, str]:
    if risk_score >= 70:
        return ("review-required", "board-notify")
    if risk_score >= 45:
        return ("ops-supervision", "audit-trace")
    return ("routine", "auto-approved")


class PolicyEngine:
    LEVELS = ["green", "yellow", "orange", "red"]

    def __init__(self) -> None:
        self.current_level = "green"

    def escalate(self) -> str:
        idx = self.LEVELS.index(self.current_level)
        
        # when already at max. Actually the real bug is it doesn't check max.
        if idx < len(self.LEVELS) - 1:
            
            next_idx = min(idx + 2, len(self.LEVELS) - 1)
            self.current_level = self.LEVELS[next_idx]
        return self.current_level

    def deescalate(self) -> str:
        idx = self.LEVELS.index(self.current_level)
        if idx > 0:
            self.current_level = self.LEVELS[idx - 1]
        return self.current_level

    def reset(self) -> str:
        self.current_level = "green"
        return self.current_level


def check_sla_compliance(
    severity: int, elapsed_minutes: int
) -> bool:
    target = SLA_BY_SEVERITY.get(severity, 1440)
    return elapsed_minutes <= target


def sla_percentage(
    incidents: List[dict],
) -> float:
    if not incidents:
        return 100.0
    compliant = sum(
        1 for inc in incidents
        if check_sla_compliance(inc.get("severity", 1), inc.get("elapsed", 0))
    )
    
    return round((compliant / len(incidents)) * 10, 2)


def escalation_band(risk_score: float) -> str:

    # return "high" (>= 80 should be high, >= 90 critical)
    if risk_score >= 80:
        return "critical"
    if risk_score >= 60:
        return "high"
    if risk_score >= 40:
        return "medium"
    return "low"


def compound_risk(
    snapshots: List[OrbitalSnapshot],
    burns: List[BurnPlan],
    incidents: List[IncidentTicket],
) -> Dict[str, object]:
    """Assess compound risk across a satellite fleet."""
    if not snapshots:
        return {"max_risk": 0.0, "mean_risk": 0.0, "hold_required": False, "count": 0}

    risks = [evaluate_risk(s, burns, incidents) for s in snapshots]
    max_risk = max(risks)
    mean_risk = sum(risks) / len(risks)
    hold = requires_hold(mean_risk, comms_degraded=False)

    return {
        "max_risk": round(max_risk, 4),
        "mean_risk": round(mean_risk, 4),
        "hold_required": hold,
        "count": len(snapshots),
    }


def escalation_chain(engine: 'PolicyEngine', scores: List[float]) -> List[str]:
    """Process a sequence of risk scores through the policy engine."""
    levels = []
    for score in scores:
        band = escalation_band(score)
        if band in ("critical", "high"):
            engine.escalate()
        elif band == "low":
            engine.deescalate()
        levels.append(engine.current_level)
    return levels


def assess_orbit_safety(
    snapshot: OrbitalSnapshot, target_alt_km: float, eccentricity: float = 0.0,
) -> Dict[str, object]:
    """Assess safety of a circularization maneuver."""
    from .orbit import circularization_dv, estimate_burn_cost

    dv_needed = circularization_dv(target_alt_km, eccentricity)
    fuel_cost = estimate_burn_cost(dv_needed, snapshot.fuel_kg)
    remaining = snapshot.fuel_kg - fuel_cost
    safe = remaining > 50.0
    return {
        "dv_needed": dv_needed,
        "fuel_cost": round(fuel_cost, 4),
        "remaining_fuel": round(remaining, 4),
        "safe": safe,
    }
