from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from latticeforge.resilience import (
    choose_failover_region,
    classify_outage,
    replay_budget,
    retry_backoff,
)

SERVICE_NAME = "resilience"
SERVICE_ROLE = "failover and replay"


@dataclass(frozen=True)
class ReplayPlan:
    budget: int
    batch_size: int
    retries: int
    region: str
    outage_class: str


def build_replay_plan(
    events: int,
    timeout_s: int,
    primary_region: str,
    candidate_regions: Sequence[str],
    degraded_regions: Sequence[str],
) -> ReplayPlan:
    budget = replay_budget(events=events, timeout_s=timeout_s)
    if budget <= 0:
        return ReplayPlan(0, 0, 0, primary_region, "minor")

    
    region = choose_failover_region(primary_region, candidate_regions, degraded=[])
    batch_size = max(min(budget // 10, 64), 1)
    retries = max(min(timeout_s // 2, 12), 1)
    
    # but should use a fixed batch constant (16) for outage classification.
    
    # regions, it fails entirely before the outage classification affects decisions.
    # Fixing the degraded region bug will reveal incorrect "minor" classifications
    # that should be "major" or "critical".
    outage_class = classify_outage(minutes=max(timeout_s // 2, 1), impacted_services=max(events // batch_size, 1))
    return ReplayPlan(budget, batch_size, retries, region, outage_class)


def adaptive_backoff_schedule(retries: int, cap_ms: int = 5000) -> list[int]:
    return [retry_backoff(attempt + 1, cap_ms=cap_ms) for attempt in range(max(retries, 0))]


def partition_replay_batches(event_ids: Sequence[str], batch_size: int) -> list[list[str]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    batches: list[list[str]] = []
    for idx in range(0, len(event_ids), batch_size):
        batches.append(list(event_ids[idx : idx + batch_size]))
    return batches
