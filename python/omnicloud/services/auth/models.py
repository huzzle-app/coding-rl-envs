"""
OmniCloud Auth Service Models
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import uuid
import time


@dataclass
class User:
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    email: str = ""
    password_hash: str = ""
    roles: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: float = field(default_factory=time.time)


@dataclass
class Role:
    role_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    permissions: List[str] = field(default_factory=list)
    inherits_from: List[str] = field(default_factory=list)  
