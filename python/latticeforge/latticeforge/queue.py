from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import List, Optional, Set


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


class BoundedPriorityChannel:
    def __init__(self, capacity: int = 100) -> None:
        self._lock = threading.Lock()
        self._items: List[QueueItem] = []
        self._inflight: List[QueueItem] = []
        self._capacity = max(capacity, 1)
        self._closed = False
        self._active_count = 0

    def send(self, ticket_id: str, severity: int, wait_seconds: int) -> bool:
        with self._lock:
            if self._closed or self._active_count >= self._capacity:
                return False
            weight = severity * 10 + min(wait_seconds, 900) / 30
            self._items.append(
                QueueItem(sort_key=-weight, ticket_id=ticket_id, severity=severity, wait_seconds=wait_seconds)
            )
            self._active_count += 1
            return True

    def drain(self, max_items: int = 10) -> List[QueueItem]:
        with self._lock:
            self._items.sort()
            batch = self._items[:max_items]
            self._items = self._items[max_items:]
            self._inflight.extend(batch)
            self._active_count -= len(batch)
            return batch

    def acknowledge(self, ticket_ids: Set[str]) -> int:
        with self._lock:
            before = len(self._inflight)
            self._inflight = [item for item in self._inflight if item.ticket_id not in ticket_ids]
            removed = before - len(self._inflight)
            self._active_count -= removed
            return removed

    def close(self) -> None:
        with self._lock:
            self._closed = True

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._items)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._items) + len(self._inflight)

    @property
    def capacity(self) -> int:
        return self._capacity
