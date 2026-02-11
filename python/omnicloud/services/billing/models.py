"""
OmniCloud Billing Service Models
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List
from decimal import Decimal
import uuid
import time


@dataclass
class Invoice:
    invoice_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    billing_period_start: float = 0.0
    billing_period_end: float = 0.0
    line_items: List[Dict[str, Any]] = field(default_factory=list)
    subtotal: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    status: str = "draft"
    created_at: float = field(default_factory=time.time)


@dataclass
class UsageRecord:
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    resource_type: str = ""
    resource_id: str = ""
    quantity: Decimal = Decimal("0")
    unit: str = "hours"
    timestamp: float = field(default_factory=time.time)
