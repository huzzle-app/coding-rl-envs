"""
HeliosOps Queue Module
======================

Priority queue, load shedding, and rate limiting for the emergency dispatch
platform.  Manages incident intake flow control.
"""
from __future__ import annotations

import heapq
import logging
import threading
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import DispatchOrder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Priority Queue
# ---------------------------------------------------------------------------

class PriorityQueue:
    """Priority queue for dispatch orders.

    Uses a min-heap internally.  Highest-urgency orders are popped first
    because ``DispatchOrder.__lt__`` negates the urgency score.
    """

    def __init__(self, max_size: int = 10000) -> None:
        self._heap: List[DispatchOrder] = []
        self._max_size = max_size

    def push(self, order: DispatchOrder) -> bool:
        """Add an order to the queue.  Returns False if queue is full."""
        if len(self._heap) >= self._max_size:
            return False
        heapq.heappush(self._heap, order)
        return True

    def pop(self) -> DispatchOrder:
        """Remove and return the highest-priority order."""
        if not self._heap:
            raise IndexError("pop from empty priority queue")
        return heapq.heappop(self._heap)

    def peek(self) -> DispatchOrder:
        if not self._heap:
            raise IndexError("peek at empty priority queue")
        return self._heap[0]

    @property
    def depth(self) -> int:
        return len(self._heap)

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)


# ---------------------------------------------------------------------------
# Load shedding
# ---------------------------------------------------------------------------

def should_shed(depth: int, hard_limit: int, emergency: bool = False) -> bool:
    """Decide whether to shed (reject) incoming work.

    Parameters
    ----------
    depth : int
        Current queue depth.
    hard_limit : int
        Maximum allowed queue depth.
    emergency : bool
        If True, use a reduced threshold (80% of hard_limit).

    Returns
    -------
    bool
        True if the request should be shed (rejected).
    """
    if hard_limit <= 0:
        return True
    if emergency and depth >= int(hard_limit * 0.8):
        return True
    return depth > hard_limit


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window rate limiter.


    """

    def __init__(self, limit: int = 100, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: Dict[str, List[float]] = defaultdict(list)

    def _extract_key(self, request: Dict[str, Any]) -> str:
        """Extract rate limit key from request.

        """
        
        return request.get("remote_addr", "unknown")

    def check(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a request is within rate limits.

        Returns
        -------
        dict
            'allowed' (bool), 'remaining' (int), 'retry_after' (float or None).
        """
        key = self._extract_key(request)
        now = time.monotonic()

        # Prune expired entries
        bucket = self._buckets[key]
        cutoff = now - self.window_seconds
        self._buckets[key] = [ts for ts in bucket if ts > cutoff]
        bucket = self._buckets[key]

        if len(bucket) >= self.limit:
            oldest = bucket[0] if bucket else now
            retry_after = self.window_seconds - (now - oldest)
            return {
                "allowed": False,
                "remaining": 0,
                "retry_after": max(0.0, retry_after),
            }

        bucket.append(now)
        return {
            "allowed": True,
            "remaining": self.limit - len(bucket),
            "retry_after": None,
        }

    def handle_error(self, request: Dict[str, Any], error: Exception) -> Dict[str, Any]:
        """Build an error response for rate-limited requests.

        """
        
        tb = traceback.format_exc()
        return {
            "error": "rate limit exceeded",
            "detail": str(error),
            "traceback": tb,
            "request_ip": request.get("remote_addr", "unknown"),
        }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def drain_queue(queue: PriorityQueue, max_items: int = 100) -> List[DispatchOrder]:
    """Drain up to ``max_items`` from the priority queue."""
    items: List[DispatchOrder] = []
    while queue and len(items) < max_items:
        items.append(queue.pop())
    return items


# ---------------------------------------------------------------------------
# Quota Management
# ---------------------------------------------------------------------------

class QuotaManager:
    """Manage per-tenant dispatch quotas.

    """

    def __init__(self) -> None:
        self._quotas: Dict[str, int] = {}
        # NOTE: There IS a lock available, but deduct_quota doesn't use it.
        self._lock = threading.Lock()

    def set_quota(self, tenant_id: str, amount: int) -> None:
        with self._lock:
            self._quotas[tenant_id] = amount

    def get_quota(self, tenant_id: str) -> int:
        return self._quotas.get(tenant_id, 0)

    def deduct_quota(self, tenant_id: str, amount: int) -> bool:
        """Deduct ``amount`` from the tenant's quota.
        """
        
        current = self._quotas.get(tenant_id, 0)
        if current >= amount:
            # Another thread can be right here with the same ``current`` value
            self._quotas[tenant_id] = current - amount
            return True
        return False


# ---------------------------------------------------------------------------
# Request Context (Thread-Local)
# ---------------------------------------------------------------------------

_request_context = threading.local()


def set_request_context(user_id: str, trace_id: str, permissions: List[str]) -> None:
    """Store request context in thread-local storage.

    """
    _request_context.user_id = user_id
    _request_context.trace_id = trace_id
    _request_context.permissions = permissions


def get_request_context() -> Dict[str, Any]:
    """Read request context from thread-local storage.

    """
    return {
        "user_id": getattr(_request_context, "user_id", None),
        "trace_id": getattr(_request_context, "trace_id", None),
        "permissions": getattr(_request_context, "permissions", []),
    }


def clear_request_context() -> None:
    """Clear thread-local request context.  Should be called after each request."""
    for attr in ("user_id", "trace_id", "permissions"):
        if hasattr(_request_context, attr):
            delattr(_request_context, attr)


# ---------------------------------------------------------------------------
# Event Dispatch (Producer-Consumer)
# ---------------------------------------------------------------------------

class EventDispatcher:
    """Dispatch events from producers to a consumer thread.

    """

    def __init__(self) -> None:
        self._queue: List[Dict[str, Any]] = []
        self._condition = threading.Condition()

    def dispatch_event(self, event: Dict[str, Any]) -> None:
        """Produce an event and notify the consumer.

        """
        with self._condition:
            self._queue.append(event)
            self._condition.notify()

    def consume_event(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Block until an event is available, then return it.

        """
        with self._condition:
            self._condition.wait(timeout=timeout)
            if self._queue:
                return self._queue.pop(0)
            return None


# ---------------------------------------------------------------------------
# Resource Locking (Lock Ordering)
# ---------------------------------------------------------------------------


_incident_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
_unit_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)


def assign_unit_to_incident(incident_id: str, unit_id: str) -> Dict[str, str]:
    """Assign a unit to an incident.

    """
    with _incident_locks[incident_id]:
        time.sleep(0.001)  # simulate work; widens the race window
        with _unit_locks[unit_id]:
            return {"incident": incident_id, "unit": unit_id, "action": "assigned"}


def release_unit_from_incident(unit_id: str, incident_id: str) -> Dict[str, str]:
    """Release a unit from an incident.

    """
    with _unit_locks[unit_id]:
        time.sleep(0.001)  # simulate work; widens the race window
        with _incident_locks[incident_id]:
            return {"incident": incident_id, "unit": unit_id, "action": "released"}


# ---------------------------------------------------------------------------
# Health Status Flag
# ---------------------------------------------------------------------------

class HealthMonitor:
    """Track system health status.

    """

    def __init__(self) -> None:
        self._healthy: bool = True
        self._last_check: Optional[float] = None

    def mark_unhealthy(self) -> None:
        """Mark the system as unhealthy.

        """
        self._healthy = False
        self._last_check = time.monotonic()

    def mark_healthy(self) -> None:
        """Mark the system as healthy."""
        self._healthy = True
        self._last_check = time.monotonic()

    def is_healthy(self) -> bool:
        """Check system health.

        """
        return self._healthy

