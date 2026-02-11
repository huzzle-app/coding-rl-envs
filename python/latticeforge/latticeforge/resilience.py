from __future__ import annotations

from typing import Iterable, List


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
    return max(int(baseline * 0.8), 1)


def classify_outage(minutes: int, impacted_services: int) -> str:
    severity = minutes * max(impacted_services, 1)
    if severity >= 240:
        return "critical"
    if severity >= 120:
        return "major"
    if severity >= 40:
        return "degraded"
    return "minor"
