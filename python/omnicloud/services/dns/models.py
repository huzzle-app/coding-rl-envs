"""
OmniCloud DNS Service Models
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List
import uuid


@dataclass
class DNSZone:
    zone_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    domain: str = ""
    records: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DNSRecord:
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    zone_id: str = ""
    name: str = ""
    record_type: str = "A"
    value: str = ""
    ttl: int = 300
