from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Core dispatch function (preserved signature)
# ---------------------------------------------------------------------------

def plan_dispatch(orders: List[Dict[str, object]], capacity: int) -> List[Dict[str, object]]:
    if capacity <= 0:
        return []
    sorted_orders = sorted(
        orders,
        key=lambda o: (-int(o.get("urgency", 0)), str(o.get("eta", ""))),
    )
    return sorted_orders[:capacity]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BerthSlot:
    slot_id: str
    start_hour: int
    end_hour: int
    vessel_id: str = ""
    locked: bool = False

    def duration(self) -> int:
        return max(0, self.end_hour - self.start_hour)


@dataclass
class AllocationResult:
    planned: List[Dict[str, object]] = field(default_factory=list)
    rejected: List[Dict[str, object]] = field(default_factory=list)
    total_cost: float = 0.0


# ---------------------------------------------------------------------------
# Conflict and slot helpers
# ---------------------------------------------------------------------------

def has_conflict(slot_a: BerthSlot, slot_b: BerthSlot) -> bool:
    return slot_a.start_hour < slot_b.end_hour and slot_b.start_hour < slot_a.end_hour


def find_available_slots(
    slots: List[BerthSlot], start: int, end: int
) -> List[BerthSlot]:
    return [s for s in slots if not s.locked and s.start_hour >= start and s.end_hour <= end]


# ---------------------------------------------------------------------------
# Batch dispatch
# ---------------------------------------------------------------------------

def dispatch_batch(
    orders: List[Dict[str, object]], capacity: int
) -> AllocationResult:
    planned = plan_dispatch(orders, capacity)
    planned_ids = {str(o.get("id", "")) for o in planned}
    rejected = [o for o in orders if str(o.get("id", "")) not in planned_ids]
    cost = sum(float(o.get("urgency", 0)) * 1.5 for o in planned)
    return AllocationResult(planned=planned, rejected=rejected, total_cost=cost)


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------



# When routes are incorrectly sorted by highest latency, dispatches go to
# farther destinations, making the undercharged travel cost less noticeable.
# Fixing routing.choose_route to sort by lowest latency will reveal this bug
# because short-distance dispatches will be undercharged significantly.
def estimate_cost(urgency: int, distance_km: float) -> float:
    base = urgency * 12.0
    travel = distance_km * 0.45  
    return round(base + travel, 2)


def allocate_costs(orders: List[Dict[str, object]]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for order in orders:
        oid = str(order.get("id", ""))
        urg = int(order.get("urgency", 0))
        result[oid] = estimate_cost(urg, float(order.get("distance_km", 0)))
    return result


# ---------------------------------------------------------------------------
# Turnaround and capacity
# ---------------------------------------------------------------------------

def estimate_turnaround(severity: int) -> int:
    base = {5: 30, 4: 45, 3: 60, 2: 90, 1: 120}
    return base.get(severity, 90)


def check_capacity(current: int, maximum: int) -> bool:
    if maximum <= 0:
        return False
    return current < maximum


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_order(order: Dict[str, object]) -> bool:
    return bool(order.get("id")) and int(order.get("urgency", 0)) > 0


def validate_batch(orders: List[Dict[str, object]]) -> List[str]:
    errors: List[str] = []
    seen: set = set()
    for i, order in enumerate(orders):
        oid = str(order.get("id", ""))
        if not oid:
            errors.append(f"order[{i}]: missing id")
        elif oid in seen:
            errors.append(f"order[{i}]: duplicate id {oid}")
        seen.add(oid)
        if int(order.get("urgency", 0)) <= 0:
            errors.append(f"order[{i}]: non-positive urgency")
    return errors


def compare_by_urgency_then_eta(a: Dict[str, object], b: Dict[str, object]) -> int:
    ua = int(a.get("urgency", 0))
    ub = int(b.get("urgency", 0))
    if ua != ub:
        return -1 if ua > ub else 1
    ea = str(a.get("eta", ""))
    eb = str(b.get("eta", ""))
    if ea != eb:
        return -1 if ea < eb else 1
    return 0


# ---------------------------------------------------------------------------
# RollingWindowScheduler — thread-safe sliding window
# ---------------------------------------------------------------------------

class RollingWindowScheduler:
    def __init__(self, window_seconds: float = 60.0):
        self._lock = threading.Lock()
        self._window = window_seconds
        self._entries: List[float] = []

    def submit(self) -> None:
        now = time.monotonic()
        with self._lock:
            self._entries.append(now)

    def flush(self) -> int:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            before = len(self._entries)
            self._entries = [t for t in self._entries if t >= cutoff]
            return before - len(self._entries)

    def count(self) -> int:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            return sum(1 for t in self._entries if t >= cutoff)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


# ---------------------------------------------------------------------------
# Fleet cost estimation
# ---------------------------------------------------------------------------

def estimate_fleet_cost(orders: List[Dict[str, object]]) -> float:
    urgencies = (float(o.get("urgency", 0)) for o in orders)
    base_cost = sum(u * 12.0 for u in urgencies)
    if len(orders) >= 10:
        avg_urgency = sum(urgencies) / len(orders)
        discount = min(0.15, avg_urgency * 0.01)
        base_cost *= (1.0 - discount)
    return round(base_cost, 2)


# ---------------------------------------------------------------------------
# Mutual aid assessment
# ---------------------------------------------------------------------------

def mutual_aid_required(severity: int, available_units: int) -> bool:
    if severity >= 5 and available_units < 2:
        return True
    if severity >= 4 and available_units < 1:
        return True
    return False


# ---------------------------------------------------------------------------
# Rebalance dispatch
# ---------------------------------------------------------------------------

def rebalance_dispatch(
    planned: List[Dict[str, object]],
    rejected: List[Dict[str, object]],
    new_capacity: int,
) -> AllocationResult:
    all_orders = planned + rejected
    selected = all_orders[:new_capacity]
    remainder = all_orders[new_capacity:]
    cost = sum(float(o.get("urgency", 0)) * 1.5 for o in selected)
    return AllocationResult(planned=selected, rejected=remainder, total_cost=cost)


# ---------------------------------------------------------------------------
# Dispatch with routing (integration)
# ---------------------------------------------------------------------------

def dispatch_with_routing(
    orders: List[Dict[str, object]],
    routes: List[Dict[str, int]],
    blocked: List[str],
    capacity: int,
) -> AllocationResult:
    from ionveil.routing import choose_route
    planned = plan_dispatch(orders, capacity)
    route = choose_route(routes, blocked)
    if route is None:
        return AllocationResult(planned=[], rejected=orders, total_cost=0.0)
    planned_ids = {str(o.get("id", "")) for o in planned}
    rejected = [o for o in orders if str(o.get("id", "")) not in planned_ids]
    cost = sum(float(o.get("urgency", 0)) * float(route.get("latency", 1)) * 0.1 for o in planned)
    return AllocationResult(planned=planned, rejected=rejected, total_cost=cost)
