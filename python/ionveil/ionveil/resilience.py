from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

# ---------------------------------------------------------------------------
# Circuit breaker states
# ---------------------------------------------------------------------------
CB_CLOSED = "closed"
CB_OPEN = "open"
CB_HALF_OPEN = "half_open"

# ---------------------------------------------------------------------------
# Core replay function (preserved signature — intentional sequence bug)
# ---------------------------------------------------------------------------

def replay_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for event in events:
        event_id = str(event["id"])
        prev = latest.get(event_id)
        if prev is None or int(event["sequence"]) < int(prev["sequence"]):
            latest[event_id] = event
    return sorted(latest.values(), key=lambda e: (int(e["sequence"]), str(e["id"])))


# ---------------------------------------------------------------------------
# Deduplication helper
# ---------------------------------------------------------------------------

T = TypeVar("T")

def deduplicate(items: List[Dict[str, Any]], key: str = "id") -> List[Dict[str, Any]]:
    seen: set = set()
    result: List[Dict[str, Any]] = []
    for item in items:
        k = item.get(key)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def merge_checkpoints(a: 'CheckpointManager', b: 'CheckpointManager') -> 'CheckpointManager':
    merged = CheckpointManager(interval=a._interval)
    all_cps: Dict[str, 'Checkpoint'] = {}
    for cp_id, cp in a._checkpoints.items():
        all_cps[cp_id] = cp
    for cp_id, cp in b._checkpoints.items():
        if cp_id in all_cps:
            if cp.timestamp > all_cps[cp_id].timestamp:
                all_cps[cp_id] = cp
        else:
            all_cps[cp_id] = cp
    for cp_id, cp in all_cps.items():
        merged.record(cp_id, cp.sequence, cp.data)
    return merged


def event_stream_diff(stream_a: List[Dict[str, Any]], stream_b: List[Dict[str, Any]], key: str = "id") -> List[Dict[str, Any]]:
    b_keys = {item.get(key) for item in stream_b}
    return [item for item in stream_a if item.get(key) not in b_keys]


def replay_converges(events_a: List[Dict[str, Any]], events_b: List[Dict[str, Any]]) -> bool:
    ra = replay_events(events_a)
    rb = replay_events(events_b)
    if len(ra) != len(rb):
        return False
    return all(
        a["id"] == b["id"] and a["sequence"] == b["sequence"]
        for a, b in zip(ra, rb)
    )


# ---------------------------------------------------------------------------
# CheckpointManager — thread-safe checkpoint tracking
# ---------------------------------------------------------------------------

@dataclass
class Checkpoint:
    checkpoint_id: str
    sequence: int
    timestamp: float
    data: Dict[str, Any]


class CheckpointManager:
    def __init__(self, interval: int = 100) -> None:
        self._lock = threading.Lock()
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._interval = interval
        self._event_count = 0

    def record(self, checkpoint_id: str, sequence: int, data: Optional[Dict[str, Any]] = None) -> Checkpoint:
        cp = Checkpoint(
            checkpoint_id=checkpoint_id,
            sequence=sequence,
            timestamp=time.monotonic(),
            data=data or {},
        )
        with self._lock:
            self._checkpoints[checkpoint_id] = cp
            self._event_count += 1
        return cp

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        with self._lock:
            return self._checkpoints.get(checkpoint_id)

    def should_checkpoint(self) -> bool:
        with self._lock:
            return self._event_count >= self._interval

    def reset(self) -> None:
        with self._lock:
            self._checkpoints.clear()
            self._event_count = 0

    def count(self) -> int:
        with self._lock:
            return len(self._checkpoints)


# ---------------------------------------------------------------------------
# CircuitBreaker — thread-safe state machine
# ---------------------------------------------------------------------------

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self._lock = threading.Lock()
        self._state = CB_CLOSED
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._last_failure_time = 0.0

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == CB_OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self._recovery_timeout:
                    self._state = CB_HALF_OPEN
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = CB_CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = CB_OPEN

    def allow_request(self) -> bool:
        s = self.state
        return s in (CB_CLOSED, CB_HALF_OPEN)

    def execute(self, fn):
        current_state = self.state
        if current_state == CB_OPEN:
            return None
        try:
            result = fn()
            if current_state == CB_HALF_OPEN:
                self.record_success()
            return result
        except Exception:
            self.record_failure()
            return None

    def reset(self) -> None:
        with self._lock:
            self._state = CB_CLOSED
            self._failure_count = 0
