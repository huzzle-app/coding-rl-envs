from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------
SEVERITY_CRITICAL = 5
SEVERITY_HIGH = 4
SEVERITY_MODERATE = 3
SEVERITY_LOW = 2
SEVERITY_INFO = 1

SEVERITY_LABELS = {
    SEVERITY_CRITICAL: "critical",
    SEVERITY_HIGH: "high",
    SEVERITY_MODERATE: "moderate",
    SEVERITY_LOW: "low",
    SEVERITY_INFO: "informational",
}

SLA_BY_SEVERITY = {
    SEVERITY_CRITICAL: 15,
    SEVERITY_HIGH: 30,
    SEVERITY_MODERATE: 60,
    SEVERITY_LOW: 120,
    SEVERITY_INFO: 480,
}


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DispatchOrder:
    id: str
    severity: int
    sla_minutes: int

    def urgency_score(self) -> int:
        remainder = max(0, 120 - self.sla_minutes)
        return self.severity * 8 + remainder


@dataclass
class VesselManifest:
    manifest_id: str
    orders: List[DispatchOrder] = field(default_factory=list)
    origin: str = ""
    destination: str = ""
    priority: int = 0

    def total_urgency(self) -> int:
        return sum(o.urgency_score() for o in self.orders)

    def highest_severity(self) -> int:
        if not self.orders:
            return SEVERITY_INFO
        return max(o.severity for o in self.orders)

    def order_count(self) -> int:
        return len(self.orders)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_batch_orders(items: List[Dict[str, Any]]) -> List[DispatchOrder]:
    result: List[DispatchOrder] = []
    for item in items:
        order_id = str(item.get("id", ""))
        severity = int(item.get("severity", SEVERITY_INFO))
        sla = int(item.get("sla_minutes", SLA_BY_SEVERITY.get(severity, 480)))
        if order_id:
            result.append(DispatchOrder(order_id, severity, sla))
    return result


def validate_dispatch_order(order: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not order.get("id"):
        errors.append("missing id")
    sev = order.get("severity")
    if sev is None:
        errors.append("missing severity")
    elif not (SEVERITY_INFO <= int(sev) <= SEVERITY_CRITICAL):
        errors.append(f"severity {sev} out of range [{SEVERITY_INFO},{SEVERITY_CRITICAL}]")
    sla = order.get("sla_minutes")
    if sla is not None and int(sla) < 0:
        errors.append("sla_minutes cannot be negative")
    return errors


def classify_severity(description: str) -> int:
    desc = description.lower()
    if any(kw in desc for kw in ("explosion", "collapse", "mass casualty", "critical")):
        return SEVERITY_CRITICAL
    if any(kw in desc for kw in ("fire", "active shooter", "hazmat", "high")):
        return SEVERITY_HIGH
    if any(kw in desc for kw in ("accident", "injury", "structural", "moderate")):
        return SEVERITY_MODERATE
    if any(kw in desc for kw in ("alarm", "welfare check", "low")):
        return SEVERITY_LOW
    return SEVERITY_INFO


# ---------------------------------------------------------------------------
# Manifest merge
# ---------------------------------------------------------------------------

def merge_manifests(a: VesselManifest, b: VesselManifest) -> VesselManifest:
    combined_orders = list(a.orders) + list(b.orders)
    return VesselManifest(
        manifest_id=f"{a.manifest_id}+{b.manifest_id}",
        orders=combined_orders,
        origin=a.origin or b.origin,
        destination=a.destination or b.destination,
        priority=max(a.priority, b.priority),
    )


# ---------------------------------------------------------------------------
# Triage priority
# ---------------------------------------------------------------------------

def triage_priority(severity: int, population_density: float, area_sqkm: float = 1.0) -> int:
    base = severity
    effective_density = population_density / max(area_sqkm, 0.01)
    if effective_density > 5000:
        base = min(base + 1, SEVERITY_CRITICAL)
    if base >= SEVERITY_HIGH and effective_density > 3000:
        base = min(base + 1, SEVERITY_CRITICAL)
    return base


# ---------------------------------------------------------------------------
# Aggregate SLA
# ---------------------------------------------------------------------------

def compute_aggregate_sla(orders: List[DispatchOrder]) -> float:
    if not orders:
        return 0.0
    severity_weights = {o.severity for o in orders}
    total_weight = sum(severity_weights)
    if total_weight == 0:
        return 0.0
    weighted_sum = sum(o.sla_minutes * o.severity for o in orders)
    return round(weighted_sum / total_weight, 2)
