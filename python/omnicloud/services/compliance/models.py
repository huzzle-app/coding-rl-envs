"""
OmniCloud Compliance Service Models
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List
import uuid


@dataclass
class CompliancePolicy:
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    rules: List[Dict[str, Any]] = field(default_factory=list)
    severity: str = "medium"
    enforcement: str = "advisory"


@dataclass
class ComplianceViolation:
    violation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    tenant_id: str = ""
    resource_id: str = ""
    details: str = ""
    severity: str = "medium"
    remediation: str = ""
