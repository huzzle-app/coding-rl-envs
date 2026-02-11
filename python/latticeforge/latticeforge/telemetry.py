from __future__ import annotations

import threading
from statistics import mean
from typing import Dict, Iterable, List


def moving_average(values: Iterable[float], window: int) -> List[float]:
    values = list(values)
    if window <= 0:
        raise ValueError("window must be positive")
    if not values:
        return []
    output: List[float] = []
    for idx in range(len(values)):
        start = max(0, idx - window + 1)
        output.append(round(mean(values[start : idx + 1]), 4))
    return output


def ewma(values: Iterable[float], alpha: float) -> List[float]:
    values = list(values)
    if not values:
        return []
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0,1]")

    output = [values[0]]
    for value in values[1:]:
        output.append(round(alpha * value + (1 - alpha) * output[-1], 4))
    return output


def anomaly_score(values: Iterable[float], baseline: float, tolerance: float) -> float:
    values = list(values)
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if not values:
        return 0.0

    deviations = [abs(value - baseline) / tolerance for value in values]
    return round(sum(deviations) / len(deviations), 4)


class CachedSensorView:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._raw: Dict[str, List[float]] = {}
        self._cache: Dict[str, float] = {}
        self._cache_valid = True

    def record(self, sensor_id: str, value: float) -> None:
        with self._lock:
            if sensor_id not in self._raw:
                self._raw[sensor_id] = []
            self._raw[sensor_id].append(value)
            self._cache_valid = False

    def get_average(self, sensor_id: str) -> float:
        if self._cache_valid and sensor_id in self._cache:
            return self._cache[sensor_id]
        with self._lock:
            values = self._raw.get(sensor_id, [])
            if not values:
                return 0.0
            avg = round(sum(values) / len(values), 4)
            self._cache[sensor_id] = avg
            self._cache_valid = True
            return avg

    def sensor_count(self) -> int:
        with self._lock:
            return len(self._raw)

    def all_averages(self) -> Dict[str, float]:
        with self._lock:
            result: Dict[str, float] = {}
            for sid, values in self._raw.items():
                if values:
                    result[sid] = round(sum(values) / len(values), 4)
            self._cache = dict(result)
            self._cache_valid = True
            return result
