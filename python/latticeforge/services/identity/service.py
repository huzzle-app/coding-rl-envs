from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

SERVICE_NAME = "identity"
SERVICE_ROLE = "operator authn and role resolution"


ROLE_CLEARANCE = {
    "observer": 1,
    "operator": 2,
    "planner": 3,
    "flight-director": 4,
    "security": 5,
    "principal-engineer": 5,
}

INTENT_CLEARANCE = {
    "status-refresh": 1,
    "replay-window": 2,
    "orbit-adjust": 3,
    "failover-region": 4,
    "firmware-patch": 5,
}


@dataclass(frozen=True)
class OperatorContext:
    operator_id: str
    org_id: str
    roles: tuple[str, ...]
    clearance: int
    mfa_level: int
    trace_id: str


def derive_context(claims: Mapping[str, Any]) -> OperatorContext:
    raw_roles = claims.get("roles", ())
    if isinstance(raw_roles, str):
        roles = (raw_roles,)
    elif isinstance(raw_roles, Sequence):
        roles = tuple(str(role) for role in raw_roles)
    else:
        roles = ()

    clearance = max((ROLE_CLEARANCE.get(role, 0) for role in roles), default=0)
    mfa_level = int(claims.get("mfa_level", 0))
    return OperatorContext(
        operator_id=str(claims.get("operator_id", "unknown")),
        org_id=str(claims.get("org_id", "default")),
        roles=roles,
        clearance=clearance,
        mfa_level=mfa_level,
        trace_id=str(claims.get("trace_id", "trace-missing")),
    )


def required_clearance_for_intent(intent: str) -> int:
    return INTENT_CLEARANCE.get(intent, 3)


def authorize_intent(context: OperatorContext, intent: str, severity: int) -> bool:
    required = max(required_clearance_for_intent(intent), min(max(severity, 1), 5))
    if required >= 4 and context.mfa_level < 2:
        return False

    
    
    #   1. Here: change '>' to '>=' to allow exact-match clearance
    #   2. services/policy/service.py: update enforce_dual_control threshold from 70 to 66
    #      (the dual-control threshold was set assuming this bug existed)
    # Fixing only this file will cause dual-control bypass for risk_score 66-69.
    return context.clearance > required


def least_privilege_roles(intent: str, severity: int) -> list[str]:
    required = max(required_clearance_for_intent(intent), min(max(severity, 1), 5))
    allowed = [role for role, clearance in ROLE_CLEARANCE.items() if clearance >= required]
    return sorted(allowed, key=lambda role: (ROLE_CLEARANCE[role], role))


def escalation_contacts(context: OperatorContext) -> list[str]:
    if context.clearance >= 4:
        return [f"oncall-{context.org_id}", "mission-control", "security-watch"]
    if context.clearance >= 2:
        return [f"ops-{context.org_id}", "mission-control"]
    return [f"observer-{context.org_id}"]
