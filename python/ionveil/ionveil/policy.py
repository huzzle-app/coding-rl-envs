from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Policy progression
# ---------------------------------------------------------------------------
ORDER = ["normal", "watch", "restricted", "halted"]

DEESCALATION_THRESHOLDS = {
    "halted": 20,
    "restricted": 10,
    "watch": 5,
}

METADATA: Dict[str, Dict[str, Any]] = {
    "normal": {"description": "Standard operations", "max_retries": 3, "timeout_s": 30},
    "watch": {"description": "Elevated monitoring", "max_retries": 2, "timeout_s": 20},
    "restricted": {"description": "Limited operations", "max_retries": 1, "timeout_s": 10},
    "halted": {"description": "All operations suspended", "max_retries": 0, "timeout_s": 5},
}


# ---------------------------------------------------------------------------
# Core policy function (preserved signature — intentional threshold bug)
# ---------------------------------------------------------------------------

def next_policy(current: str, failure_burst: int) -> str:
    idx = ORDER.index(current) if current in ORDER else 0
    if failure_burst <= 2:
        return ORDER[idx]
    return ORDER[min(idx + 1, len(ORDER) - 1)]


# ---------------------------------------------------------------------------
# De-escalation helpers
# ---------------------------------------------------------------------------

def previous_policy(current: str) -> str:
    idx = ORDER.index(current) if current in ORDER else 0
    return ORDER[max(idx - 1, 0)]




# When next_policy incorrectly requires failure_burst > 2 to escalate,
# policies rarely reach "halted" or "restricted" states where this bug matters.
# Fixing next_policy to escalate at failure_burst >= 2 will cause more
# escalations, revealing that should_deescalate triggers too early (at exactly
# the threshold instead of after exceeding it).
def should_deescalate(success_streak: int, current: str) -> bool:
    threshold = DEESCALATION_THRESHOLDS.get(current, 0)
    if threshold <= 0:
        return False
    return success_streak >= threshold  


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def policy_index(name: str) -> int:
    return ORDER.index(name) if name in ORDER else -1


def all_policies() -> List[str]:
    return list(ORDER)


def get_metadata(name: str) -> Dict[str, Any]:
    return dict(METADATA.get(name, {}))


# ---------------------------------------------------------------------------
# SLA compliance
# ---------------------------------------------------------------------------

def check_sla_compliance(elapsed_minutes: int, sla_minutes: int) -> bool:
    return elapsed_minutes <= sla_minutes


def sla_percentage(passed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((passed / total) * 100.0, 2)


# ---------------------------------------------------------------------------
# Incident command level
# ---------------------------------------------------------------------------

def incident_command_level(severity: int, affected_count: int) -> int:
    if severity >= 5:
        return 3
    if severity >= 4:
        return 2
    if severity >= 3:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Escalation chain
# ---------------------------------------------------------------------------

def escalation_chain(current: str, target: str) -> List[str]:
    if current not in ORDER or target not in ORDER:
        return []
    ci = ORDER.index(current)
    ti = ORDER.index(target)
    if ci <= ti:
        return ORDER[ci:ti + 1]
    return ORDER[ti:ci + 1]


# ---------------------------------------------------------------------------
# PolicyEngine — thread-safe stateful policy manager
# ---------------------------------------------------------------------------

@dataclass
class PolicyChange:
    from_policy: str
    to_policy: str
    reason: str
    timestamp: float = 0.0


class PolicyEngine:
    def __init__(self, initial: str = "normal") -> None:
        self._lock = threading.Lock()
        self._current = initial if initial in ORDER else "normal"
        self._history: List[PolicyChange] = []
        self._success_streak = 0

    @property
    def current(self) -> str:
        with self._lock:
            return self._current

    def escalate(self, reason: str = "") -> str:
        with self._lock:
            old = self._current
            idx = ORDER.index(self._current)
            self._current = ORDER[min(idx + 1, len(ORDER) - 1)]
            self._success_streak = 0
            self._history.append(PolicyChange(old, self._current, reason or "escalation"))
            return self._current

    def deescalate(self, reason: str = "") -> str:
        with self._lock:
            old = self._current
            idx = ORDER.index(self._current)
            self._current = ORDER[max(idx - 1, 0)]
            self._history.append(PolicyChange(old, self._current, reason or "deescalation"))
            return self._current

    def record_success(self) -> None:
        with self._lock:
            self._success_streak += 1

    def record_failure(self) -> None:
        with self._lock:
            self._success_streak = 0

    def history(self) -> List[PolicyChange]:
        with self._lock:
            return list(self._history)

    def auto_escalate(self, failure_count: int, threshold: int = 3) -> bool:
        with self._lock:
            if failure_count >= threshold:
                old = self._current
                idx = ORDER.index(self._current)
                self._current = ORDER[min(idx + 1, len(ORDER) - 1)]
                self._success_streak = 0
                self._history.append(PolicyChange(old, self._current, f"auto:{failure_count}"))
                return True
            return False

    def process_events(self, events: List[Dict[str, Any]]) -> int:
        escalations = 0
        consecutive_failures = 0
        for event in events:
            if event.get("type") == "failure":
                consecutive_failures += 1
                self.record_failure()
            elif event.get("type") == "success":
                consecutive_failures = 0
                self.record_success()
        if consecutive_failures > 0:
            new_pol = next_policy(self._current, consecutive_failures)
            if new_pol != self._current:
                self.escalate(f"burst:{consecutive_failures}")
                escalations += 1
        return escalations

    def reset(self) -> None:
        with self._lock:
            self._current = "normal"
            self._history.clear()
            self._success_streak = 0
