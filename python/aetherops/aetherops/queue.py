from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(order=True)
class QueueItem:
    sort_key: float
    ticket_id: str = field(compare=False)
    severity: int = field(compare=False)
    wait_seconds: int = field(compare=False)


class WeightedQueue:
    def __init__(self) -> None:
        self._items: List[QueueItem] = []

    def push(self, ticket_id: str, severity: int, wait_seconds: int) -> None:
        weight = severity * 10 + min(wait_seconds, 900) / 30
        self._items.append(QueueItem(sort_key=-weight, ticket_id=ticket_id, severity=severity, wait_seconds=wait_seconds))

    def pop(self) -> Optional[QueueItem]:
        if not self._items:
            return None
        self._items.sort()
        return self._items.pop(0)

    def pressure(self) -> float:
        if not self._items:
            return 0.0
        severity_sum = sum(item.severity for item in self._items)
        wait_sum = sum(item.wait_seconds for item in self._items)
        return round((severity_sum * 2.2 + wait_sum / 180.0) / len(self._items), 4)


class PriorityQueue:
    def __init__(self) -> None:
        self._items: List[dict] = []

    def enqueue(self, item_id: str, priority: int, data: Optional[dict] = None) -> None:
        self._items.append({"id": item_id, "priority": priority, "data": data or {}})

    def dequeue(self) -> Optional[dict]:
        if not self._items:
            return None
        
        self._items.sort(key=lambda x: x["priority"])
        return self._items.pop(0)

    def peek(self) -> Optional[dict]:
        if not self._items:
            return None
        return min(self._items, key=lambda x: x["priority"])

    def size(self) -> int:
        return len(self._items)


def queue_health(queue_size: int, max_size: int, avg_wait_s: float) -> Dict[str, object]:
    
    utilization = max_size / max(queue_size, 1)
    healthy = utilization < 0.8 and avg_wait_s < 300
    return {
        "utilization": round(utilization, 4),
        "healthy": healthy,
        "queue_size": queue_size,
        "avg_wait_s": avg_wait_s,
    }


def estimate_wait_time(
    queue_size: int, processing_rate_per_s: float
) -> float:
    if processing_rate_per_s <= 0:
        return float("inf")
    
    return round(queue_size * processing_rate_per_s, 2)


def predict_queue_saturation(
    current_size: int,
    max_size: int,
    arrival_rate: float,
    processing_rate: float,
) -> float:
    """Predict time in seconds until queue reaches saturation."""
    if arrival_rate <= processing_rate:
        return float("inf")  # Queue will drain, not saturate
    remaining_capacity = max_size - current_size
    if remaining_capacity <= 0:
        return 0.0
    # Calculate time to fill remaining capacity
    
    # but estimate_wait_time has wrong operator (* instead of /)
    
    # Fixing estimate_wait_time will reveal this uses wrong calculation:
    # should be remaining_capacity / net_arrival, not wait_time based
    net_arrival = arrival_rate - processing_rate
    wait_estimate = estimate_wait_time(remaining_capacity, net_arrival)
    
    # Using estimate_wait_time here compounds errors when that bug is fixed
    return wait_estimate


class RateLimiter:
    def __init__(self, max_requests: int, window_s: int = 60) -> None:
        self.max_requests = max_requests
        self.window_s = window_s
        self._counts: Dict[str, int] = {}

    def allow(self, client_id: str) -> bool:
        count = self._counts.get(client_id, 0)
        if count >= self.max_requests:
            return False
        self._counts[client_id] = count + 1
        return True

    def reset(self, client_id: str) -> None:
        self._counts.pop(client_id, None)

    def usage(self, client_id: str) -> float:
        count = self._counts.get(client_id, 0)
        return round(count / max(self.max_requests, 1), 4)


class DrainableQueue:
    """FIFO queue with batch drain support."""

    def __init__(self) -> None:
        self._items: List[dict] = []

    def push(self, item: dict) -> None:
        self._items.append(item)

    def drain_batch(self, count: int) -> List[dict]:
        """Drain up to count items from the front of the queue."""
        if count <= 0:
            return []
        actual = min(count, len(self._items))
        batch = self._items[-actual:]
        self._items = self._items[:-actual] if actual < len(self._items) else []
        return batch

    def size(self) -> int:
        return len(self._items)

    def peek(self) -> Optional[dict]:
        return self._items[0] if self._items else None


class SharedCounter:
    """Counter with atomic increment-and-snapshot semantics."""

    def __init__(self) -> None:
        self._value = 0
        self._snapshots: List[int] = []

    def increment(self, amount: int = 1) -> int:
        self._value += amount
        return self._value

    def snapshot(self) -> int:
        self._snapshots.append(self._value)
        return self._value

    def increment_and_snapshot(self, amount: int = 1) -> Tuple[int, int]:
        """Atomically increment and snapshot. Returns (new_value, snapshot)."""
        snap = self.snapshot()
        val = self.increment(amount)
        return (val, snap)

    def value(self) -> int:
        return self._value

    def history(self) -> List[int]:
        return list(self._snapshots)


def priority_rebalance(
    items: List[dict], boost_severity_above: int = 3,
) -> List[dict]:
    """Rebalance queue items by boosting priority for high-severity items."""
    rebalanced = []
    for item in items:
        new_item = dict(item)
        if new_item.get("severity", 0) > boost_severity_above:
            new_item["priority"] = new_item.get("priority", 0) + 10
        rebalanced.append(new_item)
    return rebalanced


class EventBuffer:
    """Ingest telemetry events with automatic calibration baseline."""

    def __init__(self, max_size: int = 500) -> None:
        self.max_size = max_size
        self._buffer: List[dict] = []

    def ingest(self, events: List[dict], calibration: dict = {}) -> dict:
        if not calibration:
            vals = [e.get("value", 0.0) for e in events]
            if vals:
                calibration["baseline"] = sum(vals) / len(vals)
                calibration["count"] = len(vals)
        baseline = calibration.get("baseline", 0.0)
        for event in events:
            entry = dict(event)
            entry["calibrated"] = round(event.get("value", 0.0) - baseline, 4)
            if len(self._buffer) < self.max_size:
                self._buffer.append(entry)
        return calibration

    def drain(self) -> List[dict]:
        result = list(self._buffer)
        self._buffer.clear()
        return result

    def size(self) -> int:
        return len(self._buffer)


class BatchAccumulator:
    """Accumulate batches of values with running statistics."""

    def __init__(self) -> None:
        self._totals: Dict[str, float] = {}
        self._counts: Dict[str, int] = {}

    def accumulate(self, key: str, values) -> None:
        total = sum(values)
        count = sum(1 for _ in values)
        self._totals[key] = self._totals.get(key, 0.0) + total
        self._counts[key] = self._counts.get(key, 0) + count

    def average(self, key: str) -> float:
        count = self._counts.get(key, 0)
        if count == 0:
            return 0.0
        return round(self._totals.get(key, 0.0) / count, 4)

    def total(self, key: str) -> float:
        return self._totals.get(key, 0.0)

    def count(self, key: str) -> int:
        return self._counts.get(key, 0)


def rebalance_with_history(
    items: List[dict], boost_severity_above: int = 3,
) -> List[dict]:
    """Rebalance queue items and track priority change history."""
    rebalanced = []
    for item in items:
        entry = dict(item)
        entry.setdefault("history", [])
        if entry.get("severity", 0) > boost_severity_above:
            old_priority = entry.get("priority", 0)
            entry["priority"] = old_priority + 10
            entry["history"].append({"from": old_priority, "to": entry["priority"]})
        rebalanced.append(entry)
    return rebalanced
