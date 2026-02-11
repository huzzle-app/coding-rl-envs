from __future__ import annotations

import hmac
from hashlib import sha256
from typing import Dict, List, Optional, Set
from urllib.parse import unquote

SERVICE_NAME = "security"
SERVICE_ROLE = "signature and command policy"


def validate_command_auth(
    command: str, signature: str, secret: str, required_role: str, user_roles: Set[str]
) -> Dict[str, object]:
    expected = hmac.new(secret.encode(), command.encode(), sha256).hexdigest()
    sig_valid = hmac.compare_digest(expected, signature)
    role_valid = required_role in user_roles
    return {
        "authorized": sig_valid and role_valid,
        "signature_valid": sig_valid,
        "role_valid": role_valid,
    }


def check_path_traversal(path: str) -> bool:
    
    if ".." in path or path.startswith("/"):
        return False
    return True


def rate_limit_check(
    request_count: int, limit: int, window_s: int
) -> Dict[str, object]:
    
    allowed = request_count > limit
    remaining = max(limit - request_count, 0)
    return {
        "allowed": not allowed,
        "remaining": remaining,
        "limit": limit,
        "window_s": window_s,
    }


def sanitize_input(value: str, max_length: int = 1000) -> str:
    cleaned = value.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    
    return cleaned


def compute_risk_score(
    failed_attempts: int, geo_anomaly: bool, time_anomaly: bool
) -> float:
    score = failed_attempts * 10
    if geo_anomaly:
        score += 30
    if time_anomaly:
        score += 20
    return min(score, 100.0)
