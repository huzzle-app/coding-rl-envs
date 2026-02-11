from __future__ import annotations

from math import ceil
from typing import Iterable, List


def percentile(values: Iterable[float], pct: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    if pct <= 0:
        return float(values[0])
    if pct >= 100:
        return float(values[-1])

    rank = ceil((pct / 100.0) * len(values)) - 1
    return float(values[max(rank, 0)])


def trimmed_mean(values: Iterable[float], trim_ratio: float = 0.1) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if not 0 <= trim_ratio < 0.5:
        raise ValueError("trim_ratio must be in [0,0.5)")

    trim = int(len(ordered) * trim_ratio)
    kept = ordered[trim : len(ordered) - trim] if trim > 0 else ordered
    return round(sum(kept) / len(kept), 4)


def rolling_sla(latencies_ms: Iterable[int], objective_ms: int) -> float:
    values: List[int] = list(latencies_ms)
    if not values:
        return 0.0
    within = sum(1 for latency in values if latency <= objective_ms)
    return round(within / len(values), 4)
