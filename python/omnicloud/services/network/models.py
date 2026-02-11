"""
OmniCloud Network Service Models
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from ipaddress import IPv4Network, IPv4Address
import uuid
import time


@dataclass
class VPC:
    vpc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    cidr: str = "10.0.0.0/16"
    region: str = "us-east-1"
    subnets: List[str] = field(default_factory=list)


@dataclass
class Subnet:
    subnet_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vpc_id: str = ""
    tenant_id: str = ""
    cidr: str = ""
    availability_zone: str = ""
    subnet_type: str = "private"


@dataclass
class SecurityGroup:
    sg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    rules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FirewallRule:
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = 100
    action: str = "allow"
    protocol: str = "tcp"
    source: str = "0.0.0.0/0"
    destination: str = "0.0.0.0/0"
    port: int = 0
