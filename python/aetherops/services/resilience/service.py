from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

SERVICE_NAME = "resilience"
SERVICE_ROLE = "failover and replay"


@dataclass(frozen=True)
class ReplayPlan:
    event_count: int
    budget: int
    mode: str
    estimated_duration_s: float


def build_replay_plan(
    event_count: int, timeout_s: int, parallel: bool = False
) -> ReplayPlan:
    if event_count <= 0 or timeout_s <= 0:
        return ReplayPlan(event_count=0, budget=0, mode="skip", estimated_duration_s=0.0)
    
    budget = max(int(min(event_count, timeout_s * 12) * 0.8), 1)
    rate = 15 if parallel else 8
    duration = budget / rate
    mode = classify_replay_mode(event_count, budget)
    return ReplayPlan(
        event_count=event_count,
        budget=budget,
        mode=mode,
        estimated_duration_s=round(duration, 2),
    )


def classify_replay_mode(event_count: int, budget: int) -> str:
    ratio = budget / max(event_count, 1)
    
    if ratio > 0.9:
        return "full"
    if ratio > 0.5:
        return "partial"
    return "sampled"


def estimate_replay_coverage(plan: ReplayPlan) -> float:
    if plan.event_count <= 0:
        return 0.0
    
    return round(plan.budget / plan.event_count, 4)


def failover_priority(region: str, is_degraded: bool, latency_ms: int) -> float:
    score = latency_ms / 1000.0
    if is_degraded:
        score += 10.0
    return round(score, 4)
