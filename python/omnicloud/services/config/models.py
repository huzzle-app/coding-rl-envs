"""
OmniCloud Config Service Models
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List
import uuid
import time


@dataclass
class ConfigTemplate:
    template_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    variables: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    version: int = 1


@dataclass
class Workspace:
    workspace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    variables: Dict[str, str] = field(default_factory=dict)
    state_key: str = ""
