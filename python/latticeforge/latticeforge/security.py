from __future__ import annotations

import hmac
import os
from hashlib import sha256


def requires_mfa(role: str, severity: int) -> bool:
    privileged = role in {"flight-director", "security", "principal-engineer"}
    return privileged or severity >= 4


def validate_command_signature(command: str, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), command.encode("utf-8"), sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def sanitize_target_path(path: str) -> str:
    normalized = os.path.normpath(path)
    if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        raise ValueError("unsafe path")
    return normalized.replace("\\", "/")
