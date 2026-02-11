from __future__ import annotations

import hashlib
import hmac
import os
import threading
import time
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Allowed origins for CORS
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    "https://ionveil.internal",
    "https://dispatch.ionveil.internal",
    "https://admin.ionveil.internal",
]

# ---------------------------------------------------------------------------
# Core signature verification (preserved signature)
# ---------------------------------------------------------------------------

def verify_signature(payload: str, signature: str, expected: str) -> bool:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, signature) and hmac.compare_digest(signature, expected)


# ---------------------------------------------------------------------------
# HMAC manifest signing
# ---------------------------------------------------------------------------

def sign_manifest(payload: str, key: str) -> str:
    return hmac.new(key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_manifest(payload: str, signature: str, key: str) -> bool:
    expected = sign_manifest(payload, key)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Path sanitisation
# ---------------------------------------------------------------------------

def sanitise_path(path: str) -> str:
    cleaned = path.replace("\\", "/")
    parts = []
    for part in cleaned.split("/"):
        if part in ("", ".", ".."):
            continue
        parts.append(part)
    return "/".join(parts)


# ---------------------------------------------------------------------------
# Origin check
# ---------------------------------------------------------------------------

def is_allowed_origin(origin: str) -> bool:
    return origin in ALLOWED_ORIGINS


# ---------------------------------------------------------------------------
# TokenStore — thread-safe token management
# ---------------------------------------------------------------------------

class TokenStore:
    def __init__(self, default_ttl: float = 3600.0) -> None:
        self._lock = threading.Lock()
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl

    def store(self, token: str, metadata: Optional[Dict[str, Any]] = None, ttl: Optional[float] = None) -> None:
        with self._lock:
            self._tokens[token] = {
                "metadata": metadata or {},
                "created": time.monotonic(),
                "ttl": ttl if ttl is not None else self._default_ttl,
            }

    def validate(self, token: str) -> bool:
        with self._lock:
            entry = self._tokens.get(token)
            if entry is None:
                return False
            elapsed = time.monotonic() - entry["created"]
            return elapsed < entry["ttl"]

    def revoke(self, token: str) -> bool:
        with self._lock:
            return self._tokens.pop(token, None) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._tokens)

    def transfer(self, token: str, new_store: 'TokenStore') -> bool:
        with self._lock:
            entry = self._tokens.pop(token, None)
        if entry is None:
            return False
        import time as _time
        elapsed = _time.monotonic() - entry["created"]
        remaining_ttl = entry["ttl"] - elapsed
        if remaining_ttl <= 0:
            return False
        new_store.store(token, entry["metadata"])
        return True

    def cleanup(self) -> int:
        now = time.monotonic()
        with self._lock:
            expired = [
                k for k, v in self._tokens.items()
                if (now - v["created"]) >= v["ttl"]
            ]
            for k in expired:
                del self._tokens[k]
            return len(expired)
