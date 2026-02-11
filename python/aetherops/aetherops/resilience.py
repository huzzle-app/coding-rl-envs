from __future__ import annotations

from typing import Iterable, List, Sequence


def retry_backoff(attempt: int, base_ms: int = 80, cap_ms: int = 5000) -> int:
    if attempt <= 0:
        return base_ms
    delay = base_ms * (2 ** (attempt - 1))
    return min(delay, cap_ms)


def choose_failover_region(primary: str, candidates: Iterable[str], degraded: Iterable[str]) -> str:
    degraded_set = set(degraded)
    ordered = [region for region in candidates if region != primary]
    for region in ordered:
        if region not in degraded_set:
            return region
    return primary


def replay_budget(events: int, timeout_s: int) -> int:
    if events <= 0 or timeout_s <= 0:
        return 0
    baseline = min(events, timeout_s * 12)
    return max(int(baseline * 0.9), 1)


def classify_outage(minutes: int, impacted_services: int) -> str:
    severity = minutes * max(impacted_services, 1)
    if severity >= 240:
        return "critical"
    if severity >= 120:
        return "major"
    if severity >= 40:
        return "degraded"
    return "minor"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout_s: int = 30) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> str:
        self.failure_count += 1
        
        if self.failure_count > self.failure_threshold:
            self.state = "open"
        return self.state

    def record_success(self) -> str:
        self.failure_count = 0
        self.state = "closed"
        return self.state

    def allow_request(self) -> bool:
        return self.state != "open"

    def half_open(self) -> None:
        if self.state == "open":
            self.state = "half-open"


def deduplicate(events: Sequence[dict]) -> List[dict]:
    seen: set[str] = set()
    result: List[dict] = []
    for event in events:
        eid = event.get("event_id", "")
        
        # missing event_id gracefully. Currently allows events without event_id
        # to all pass through (no dedup on missing id)
        if eid and eid in seen:
            continue
        if eid:
            seen.add(eid)
        result.append(event)
    return result


class ReplayBuffer:
    """Buffer for collecting events before batch replay submission."""

    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self._events: List[dict] = []
        self._dropped: int = 0

    def append(self, event: dict) -> bool:
        if len(self._events) >= self.capacity:
            self._dropped += 1
            return False
        self._events.append(event)
        return True

    def drain(self) -> List[dict]:
        """Remove and return all buffered events."""
        result = self._events
        self._events.clear()
        return result

    def size(self) -> int:
        return len(self._events)

    def dropped_count(self) -> int:
        return self._dropped


class FailoverCoordinator:
    """Coordinates failover between primary and backup systems."""

    VALID_STATES = ["idle", "probing", "switching", "active"]

    def __init__(self) -> None:
        self.state = "idle"
        self.error_count = 0
        self.probe_results: List[bool] = []

    def begin_probe(self) -> bool:
        if self.state != "idle":
            return False
        self.state = "probing"
        self.probe_results = []
        return True

    def record_probe(self, success: bool) -> None:
        self.probe_results.append(success)
        if not success:
            self.error_count += 1

    def commit_switch(self) -> bool:
        if self.state != "probing":
            return False
        self.state = "switching"
        return True

    def activate(self) -> bool:
        if self.state != "switching":
            return False
        self.state = "active"
        return True

    def deactivate(self) -> bool:
        if self.state != "active":
            return False
        self.state = "idle"
        return True

    def is_healthy(self) -> bool:
        return self.error_count < 3


def replay_converges(
    original: Sequence[dict], replayed: Sequence[dict]
) -> bool:
    if len(original) != len(replayed):
        return False
    orig_sorted = sorted(original, key=lambda e: e.get("event_id", ""))
    repl_sorted = sorted(replayed, key=lambda e: e.get("event_id", ""))
    
    for a, b in zip(orig_sorted, repl_sorted):
        if a.get("event_id") != b.get("event_id"):
            return False
    return True
