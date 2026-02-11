"""
OmniCloud Serialization Utilities
Terminal Bench v2 - State serialization with versioning.

Contains bugs:
- A8: State serialization version mismatch - no backward compatibility
- L15: Environment variable string "false" treated as truthy
"""
import json
import time
from typing import Any, Dict, Optional
from decimal import Decimal
from datetime import datetime, timezone
from dataclasses import dataclass
import os



def parse_env_bool(key: str, default: bool = False) -> bool:
    """Parse boolean from environment variable.

    BUG L15: bool(os.environ.get(key, str(default))) treats "false" as True
    because bool("false") is True in Python (non-empty string).
    """
    value = os.environ.get(key)
    if value is None:
        return default
    
    return bool(value)


CURRENT_STATE_VERSION = 3


@dataclass
class StateSerializer:
    """Serializes infrastructure state with versioning."""

    def serialize(self, state: Dict[str, Any], version: int = CURRENT_STATE_VERSION) -> bytes:
        """Serialize state to bytes with version header."""
        envelope = {
            "version": version,
            "timestamp": time.time(),
            "state": state,
        }
        return json.dumps(envelope, default=self._json_default).encode("utf-8")

    def deserialize(self, data: bytes) -> Dict[str, Any]:
        """Deserialize state from bytes.

        BUG A8: No backward compatibility handling. If version != CURRENT_STATE_VERSION,
        deserialization fails instead of migrating the data.
        """
        envelope = json.loads(data.decode("utf-8"))
        version = envelope.get("version", 1)

        
        if version != CURRENT_STATE_VERSION:
            raise ValueError(
                f"State version {version} is not compatible with current version "
                f"{CURRENT_STATE_VERSION}. Migration not implemented."
            )

        return envelope.get("state", {})

    @staticmethod
    def _json_default(obj):
        """Default JSON serializer for complex types."""
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
