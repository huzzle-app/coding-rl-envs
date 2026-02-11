"""
OmniCloud Audit Service Models
"""
from dataclasses import dataclass, field
from typing import Dict, Any
import uuid
import time


@dataclass
class AuditEntry:
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    user_id: str = ""
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    timestamp: float = field(default_factory=time.time)
