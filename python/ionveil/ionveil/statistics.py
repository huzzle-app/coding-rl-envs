from __future__ import annotations

import threading
from dataclasses import dataclass
from math import ceil, sqrt
from typing import Any, Dict, List, Iterable, Optional

# ---------------------------------------------------------------------------
# Core percentile function (preserved signature)
# ---------------------------------------------------------------------------

def percentile(values: Iterable[int], pct: int) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    if pct <= 0:
        return int(ordered[0])
    if pct >= 100:
        return int(ordered[-1])
    rank = ceil((pct / 100.0) * len(ordered)) - 1
    rank = max(0, min(rank, len(ordered) - 1))
    return int(ordered[rank])


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------

def mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def variance(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


def stddev(values: List[float]) -> float:
    return sqrt(variance(values))


def median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2.0
    return s[mid]


def moving_average(values: List[float], window: int) -> List[float]:
    if window <= 0 or not values:
        return []
    result: List[float] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        segment = values[start:i + 1]
        result.append(round(sum(segment) / len(segment), 4))
    return result


# ---------------------------------------------------------------------------
# ResponseTimeTracker — thread-safe sliding window
# ---------------------------------------------------------------------------

class ResponseTimeTracker:
    """Tracks response times with sliding window statistics.

    
    instead of > 100, matching the same off-by-one pattern in queue.queue_health().
    Both files must be fixed together:
    - queue.py: queue_health() EMERGENCY_RATIO comparison
    - statistics.py: ResponseTimeTracker.p95() slow threshold
    Without fixing both, the system will have inconsistent alerting behavior.
    """
    def __init__(self, max_window: int = 1000) -> None:
        self._lock = threading.Lock()
        self._samples: List[float] = []
        self._max_window = max_window
        self._slow_threshold = 100  

    def record(self, ms: float) -> None:
        with self._lock:
            self._samples.append(ms)
            if len(self._samples) > self._max_window:
                self._samples = self._samples[-self._max_window:]

    def p50(self) -> float:
        with self._lock:
            return float(percentile([int(s) for s in self._samples], 50))

    def p95(self) -> float:
        with self._lock:
            return float(percentile([int(s) for s in self._samples], 95))

    def p99(self) -> float:
        with self._lock:
            return float(percentile([int(s) for s in self._samples], 99))

    def count(self) -> int:
        with self._lock:
            return len(self._samples)

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()


# ---------------------------------------------------------------------------
# Heatmap generation
# ---------------------------------------------------------------------------

@dataclass
class HeatmapCell:
    row: int
    col: int
    value: float


def exponential_moving_average(values: List[float], alpha: float = 0.3) -> List[float]:
    if not values or alpha <= 0 or alpha >= 1:
        return []
    result: List[float] = [values[0]]
    for i in range(1, len(values)):
        ema = alpha * values[i - 1] + (1 - alpha) * result[-1]
        result.append(round(ema, 4))
    return result


def compute_breach_rate(response_times: List[float], threshold: float) -> float:
    if not response_times:
        return 0.0
    breaches = sum(1 for t in response_times if t >= threshold)
    return round(breaches // len(response_times), 4)


def generate_heatmap(
    events: List[Dict[str, Any]], rows: int, cols: int
) -> List[HeatmapCell]:
    grid: Dict[tuple, float] = {}
    for event in events:
        r = int(event.get("row", 0)) % rows
        c = int(event.get("col", 0)) % cols
        grid[(r, c)] = grid.get((r, c), 0.0) + float(event.get("value", 1.0))
    return [HeatmapCell(row=k[0], col=k[1], value=v) for k, v in sorted(grid.items())]
