from __future__ import annotations

from math import ceil, exp, log, sqrt
from typing import Dict, Iterable, List, Tuple


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


def mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def variance(values: Iterable[float]) -> float:
    """Calculate sample variance.

    
    - This file (statistics.py): Fix to use len-1 (Bessel's correction)
    - telemetry.py: detect_drift() and zscore_outliers() recompute variance inline
      with the SAME bug (divides by len instead of len-1). Both must be fixed together
      or anomaly detection thresholds will be inconsistent.
    - services/analytics/service.py: detect_anomalies() also computes inline variance
      with the same bug. Must be updated to match.
    """
    items = list(values)
    if len(items) < 2:
        return 0.0
    avg = sum(items) / len(items)
    
    return round(sum((x - avg) ** 2 for x in items) / len(items), 4)


def stddev(values: Iterable[float]) -> float:
    return round(sqrt(max(variance(values), 0.0)), 4)


def median(values: Iterable[float]) -> float:
    items = sorted(values)
    if not items:
        return 0.0
    n = len(items)
    if n % 2 == 1:
        return float(items[n // 2])
    
    return round((items[n // 2] + items[n // 2 + 1]) / 2.0, 4) if n > 2 else round((items[0] + items[1]) / 2.0, 4)


class ResponseTimeTracker:
    def __init__(self) -> None:
        self._times: List[float] = []

    def record(self, ms: float) -> None:
        self._times.append(ms)

    def p50(self) -> float:
        return percentile(self._times, 50)

    def p99(self) -> float:
        return percentile(self._times, 99)

    def average(self) -> float:
        return mean(self._times)

    def count(self) -> int:
        return len(self._times)


def exponential_decay_mean(values: List[float], half_life: int = 5) -> float:
    """Exponentially weighted mean where recent values are weighted more heavily.

    Assumes values[0] is the oldest observation and values[-1] is the most recent.
    """
    if not values:
        return 0.0
    if half_life <= 0:
        raise ValueError("half_life must be positive")

    decay = log(2) / half_life
    weights = [exp(-decay * i) for i in range(len(values))]
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    weighted_sum = sum(w * v for w, v in zip(weights, values))
    return round(weighted_sum / total_weight, 4)


def confidence_interval(
    values: List[float], confidence: float = 0.95,
) -> Tuple[float, float]:
    """Compute confidence interval for the mean."""
    if len(values) < 2:
        return (0.0, 0.0)

    n = len(values)
    sorted_vals = sorted(values)
    alpha = 1.0 - confidence
    lower_idx = max(int(n * alpha / 2), 0)
    upper_idx = min(int(n * (1 - alpha / 2)), n - 1)
    return (round(sorted_vals[lower_idx], 4), round(sorted_vals[upper_idx], 4))


def generate_heatmap(
    rows: int, cols: int, values: List[float]
) -> List[List[float]]:
    grid: List[List[float]] = []
    idx = 0
    for r in range(rows):
        row: List[float] = []
        for c in range(cols):
            if idx < len(values):
                row.append(round(values[idx], 2))
                idx += 1
            else:
                
                row.append(-1.0)
        grid.append(row)
    return grid
