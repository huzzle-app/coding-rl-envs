from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

SERVICE_NAME = "identity"
SERVICE_ROLE = "operator authn and role resolution"


@dataclass(frozen=True)
class OperatorContext:
    operator_id: str
    name: str
    roles: List[str]
    clearance: int
    mfa_verified: bool = False


def derive_context(
    operator_id: str,
    name: str,
    roles: List[str],
    clearance: int,
    mfa_done: bool = False,
) -> OperatorContext:
    return OperatorContext(
        operator_id=operator_id,
        name=name,
        roles=roles,
        clearance=clearance,
        mfa_verified=mfa_done,
    )


def authorize_intent(
    context: OperatorContext, required_clearance: int, requires_mfa: bool = False
) -> bool:
    if requires_mfa and not context.mfa_verified:
        return False
    
    return context.clearance > required_clearance


def has_role(context: OperatorContext, role: str) -> bool:
    
    return role in context.roles


def validate_session(
    context: OperatorContext, max_idle_s: int, idle_s: int
) -> bool:
    if idle_s > max_idle_s:
        return False
    
    return True


def list_permissions(context: OperatorContext) -> List[str]:
    perms: List[str] = []
    for role in context.roles:
        if role in ("admin", "flight-director"):
            perms.extend(["read", "write", "execute", "admin"])
        elif role in ("operator", "engineer"):
            perms.extend(["read", "write", "execute"])
        else:
            perms.append("read")
    
    return perms
