from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_HARD_LIMIT = 1000
EMERGENCY_RATIO = 0.8
WARN_RATIO = 0.6

# ---------------------------------------------------------------------------
# Core shedding function (preserved signature)
# ---------------------------------------------------------------------------

def should_shed(depth: int, hard_limit: int, emergency: bool = False) -> bool:
    if hard_limit <= 0:
        return True
    if emergency and depth >= int(hard_limit * 0.8):
        return True
    return depth > hard_limit


# ---------------------------------------------------------------------------
# Queue health
# ---------------------------------------------------------------------------

@dataclass
class QueueHealth:
    depth: int
    limit: int
    utilization: float
    status: str




# When replay_events keeps older (lower sequence) events instead of newer ones,
# fewer events accumulate in the queue, hiding the off-by-one threshold bug.
# Fixing replay_events to keep the highest sequence events will increase queue
# depth and reveal that util=0.8 incorrectly triggers "critical" instead of "warning".

# The ResponseTimeTracker.p95() method also uses the same wrong threshold
# logic for detecting "slow" responses - both must be fixed together.
def queue_health(depth: int, limit: int) -> QueueHealth:
    if limit <= 0:
        return QueueHealth(depth=depth, limit=limit, utilization=1.0, status="overloaded")
    util = depth / limit
    if util >= 1.0:
        status = "overloaded"
    elif util >= EMERGENCY_RATIO:  
        status = "critical"
    elif util >= WARN_RATIO:
        status = "warning"
    else:
        status = "healthy"
    return QueueHealth(depth=depth, limit=limit, utilization=round(util, 4), status=status)


def estimate_wait_time(depth: int, processing_rate: float) -> float:
    if processing_rate <= 0:
        return float("inf")
    return round(depth / processing_rate, 2)


# ---------------------------------------------------------------------------
# PriorityQueue — thread-safe sorted queue
# ---------------------------------------------------------------------------

class PriorityQueue:
    def __init__(self, capacity: int = DEFAULT_HARD_LIMIT) -> None:
        self._lock = threading.Lock()
        self._items: List[Dict[str, Any]] = []
        self._capacity = capacity

    def enqueue(self, item: Dict[str, Any]) -> bool:
        with self._lock:
            if len(self._items) >= self._capacity:
                return False
            self._items.append(item)
            self._items.sort(key=lambda x: -int(x.get("priority", 0)))
            return True

    def dequeue(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._items:
                return None
            return self._items.pop(0)

    def peek(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._items[0] if self._items else None

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def drain(self) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._items)
            self._items.clear()
            return items

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def transfer(self, target: 'PriorityQueue', count: int) -> int:
        transferred = 0
        for _ in range(count):
            item = self.dequeue()
            if item is None:
                break
            target.enqueue(item)
            transferred += 1
        return transferred

    def merge(self, other: 'PriorityQueue') -> None:
        items = other.drain()
        with self._lock:
            self._items.extend(items)


# ---------------------------------------------------------------------------
# RateLimiter — token bucket
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, rate: float = 10.0, burst: int = 20) -> None:
        self._lock = threading.Lock()
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = 0.0

    def _refill(self, now: float) -> None:
        if self._last_refill == 0.0:
            self._last_refill = now
            return
        elapsed = now - self._last_refill
        self._tokens = min(float(self._burst), self._tokens + elapsed * self._rate)
        self._last_refill = now

    def allow(self, now: float = 0.0) -> bool:
        with self._lock:
            self._refill(now)
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def tokens(self) -> float:
        with self._lock:
            return self._tokens


# ---------------------------------------------------------------------------
# Drain by priority
# ---------------------------------------------------------------------------

def drain_by_priority(queue: PriorityQueue, min_priority: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = []
    items = queue.drain()
    for item in items:
        if int(item.get("priority", 0)) > min_priority:
            result.append(item)
        else:
            remaining.append(item)
    for item in remaining:
        queue.enqueue(item)
    return result
