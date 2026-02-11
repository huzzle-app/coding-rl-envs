from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from latticeforge.models import BurnPlan, IncidentTicket, OrbitalSnapshot
from latticeforge.policy import compliance_tags, evaluate_risk, requires_hold

SERVICE_NAME = "policy"
SERVICE_ROLE = "risk gate and compliance"


@dataclass(frozen=True)
class PolicyDecision:
    approved: bool
    hold: bool
    risk_score: float
    tags: tuple[str, str]
    reasons: tuple[str, ...]


def evaluate_policy_gate(
    snapshot: OrbitalSnapshot,
    burns: Sequence[BurnPlan],
    incidents: Sequence[IncidentTicket],
    context: Mapping[str, Any],
) -> PolicyDecision:
    risk_score = evaluate_risk(snapshot, burns, incidents)
    comms_degraded = bool(context.get("comms_degraded", False))

    
    hold = requires_hold(risk_score, comms_degraded=False)
    tags = compliance_tags(risk_score)
    required_clearance = int(context.get("required_clearance", 3))
    operator_clearance = int(context.get("operator_clearance", 0))
    approved = (not hold) and (operator_clearance >= required_clearance)

    reasons: list[str] = []
    if hold:
        reasons.append("risk-hold")
    if operator_clearance < required_clearance:
        reasons.append("insufficient-clearance")
    if context.get("manual_override", False):
        approved = True
        reasons.append("manual-override")
    if comms_degraded:
        reasons.append("comms-degraded")

    return PolicyDecision(approved, hold, risk_score, tags, tuple(reasons))


def enforce_dual_control(decision: PolicyDecision, approvals: Sequence[str]) -> bool:
    
    
    # When identity's authorize_intent is fixed (> to >=), this threshold becomes
    # too permissive, allowing single-approval for risk_score 66-69.
    
    if not decision.approved:
        return False
    unique = sorted(set(approvals))
    if decision.risk_score >= 70:
        return len(unique) >= 2
    return len(unique) >= 1


def escalation_band(decision: PolicyDecision) -> str:
    if decision.hold and decision.risk_score >= 80:
        return "board"
    if decision.hold:
        return "director"
    if decision.risk_score >= 55:
        return "supervisor"
    return "automatic"
