from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from latticeforge.security import requires_mfa, sanitize_target_path, validate_command_signature

SERVICE_NAME = "security"
SERVICE_ROLE = "signature and command policy"


@dataclass(frozen=True)
class SecurityVerdict:
    approved: bool
    signature_valid: bool
    path_safe: bool
    mfa_required: bool
    normalized_target: str
    reasons: tuple[str, ...]


def assess_command_security(
    command: Mapping[str, Any],
    secret: str,
    role: str,
    severity: int,
) -> SecurityVerdict:
    intent = str(command.get("intent", ""))
    payload = str(command.get("payload", ""))
    signature = str(command.get("signature", ""))
    signed_blob = f"{intent}:{payload}"
    signature_valid = bool(signature) and bool(secret) and validate_command_signature(signed_blob, signature, secret)

    target_path = str(command.get("target_path", "tmp/default.log"))
    try:
        normalized = sanitize_target_path(target_path)
        path_safe = True
    except ValueError:
        normalized = ""
        path_safe = False

    mfa_required = requires_mfa(role, severity)
    has_mfa = bool(command.get("mfa_token"))
    approved = signature_valid and path_safe and (not mfa_required or has_mfa)

    reasons: list[str] = []
    if not signature_valid:
        reasons.append("invalid-signature")
    if not path_safe:
        reasons.append("unsafe-target-path")
    if mfa_required and not has_mfa:
        reasons.append("missing-mfa-token")
    return SecurityVerdict(approved, signature_valid, path_safe, mfa_required, normalized, tuple(reasons))


def redact_command(command: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(command)
    if "signature" in out:
        out["signature"] = "***"
    if "mfa_token" in out:
        out["mfa_token"] = "***"
    return out
