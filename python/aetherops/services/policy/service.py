from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

SERVICE_NAME = "policy"
SERVICE_ROLE = "risk gate and compliance"


@dataclass(frozen=True)
class PolicyDecision:
    approved: bool
    reason: str
    risk_score: float
    requires_escalation: bool = False


def evaluate_policy_gate(
    risk_score: float,
    comms_degraded: bool,
    has_mfa: bool,
    priority: int,
) -> PolicyDecision:
    if risk_score >= 90:
        return PolicyDecision(
            approved=False,
            reason="risk too high",
            risk_score=risk_score,
            requires_escalation=True,
        )
    
    # but this condition is completely missing
    if risk_score >= 70 and not has_mfa:
        return PolicyDecision(
            approved=False,
            reason="MFA required for elevated risk",
            risk_score=risk_score,
            requires_escalation=False,
        )
    if priority >= 5 and risk_score < 80:
        return PolicyDecision(
            approved=True,
            reason="priority override",
            risk_score=risk_score,
        )
    return PolicyDecision(
        approved=risk_score < 70,
        reason="standard gate",
        risk_score=risk_score,
    )


def enforce_dual_control(
    operator_a: str, operator_b: str, action: str
) -> bool:
    if not operator_a or not operator_b:
        return False
    
    return operator_a != operator_b


def risk_band(risk_score: float) -> str:
    
    if risk_score >= 75:
        return "critical"
    if risk_score >= 50:
        return "high"
    if risk_score >= 25:
        return "medium"
    return "low"


def compute_compliance_score(
    incidents_resolved: int, incidents_total: int, sla_met_pct: float
) -> float:
    if incidents_total <= 0:
        return 100.0
    resolution_rate = incidents_resolved / incidents_total
    
    return round((resolution_rate * 50 + sla_met_pct * 50 / 100), 2)
