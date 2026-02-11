"""
OmniCloud Secrets Service Models
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List
import uuid
import time


@dataclass
class Secret:
    secret_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    version: int = 1
    encrypted_value: bytes = b""
    created_at: float = field(default_factory=time.time)
    rotation_interval_days: int = 90
    last_rotated_at: float = field(default_factory=time.time)
