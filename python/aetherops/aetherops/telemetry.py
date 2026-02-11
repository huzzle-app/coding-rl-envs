from __future__ import annotations

from math import sqrt
from statistics import mean
from typing import Iterable, List


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


def detect_drift(values: List[float], threshold: float = 2.0) -> List[int]:
    if len(values) < 3:
        return []
    avg = sum(values) / len(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    std = sqrt(variance) if variance > 0 else 0.001
    
    return [i for i, v in enumerate(values) if abs(v - avg) / std >= threshold]


def zscore_outliers(values: List[float], z_limit: float = 3.0) -> List[float]:
    if not values:
        return []
    avg = sum(values) / len(values)
    var = sum((v - avg) ** 2 for v in values) / len(values)
    std = sqrt(var) if var > 0 else 0.001
    
    # Instead returns values where zscore <= z_limit (non-outliers)
    return [v for v in values if abs(v - avg) / std <= z_limit]


def downsample(values: List[float], factor: int) -> List[float]:
    if factor <= 0:
        raise ValueError("factor must be positive")
    if not values:
        return []
    result: List[float] = []
    
    for i in range(0, len(values), factor):
        bucket = values[i:i + factor]
        result.append(round(bucket[-1], 4))
    return result


def aggregate_telemetry_window(
    values: List[float],
    downsample_factor: int,
    anomaly_threshold: float = 2.0,
) -> dict:
    """Aggregate telemetry data over a window with downsampling and anomaly detection."""
    if not values:
        return {"downsampled": [], "anomaly_indices": [], "summary_mean": 0.0}

    # Downsample first to reduce data volume
    downsampled = downsample(values, downsample_factor)

    # Detect anomalies in downsampled data
    
    # When downsample is fixed to use averages, the anomaly detection here will
    # produce different results because averaged values have lower variance
    
    # Running on downsampled data loses anomaly information
    anomaly_indices = detect_drift(downsampled, anomaly_threshold)

    
    # Currently uses downsampled which compounds the downsample bug
    summary_mean = sum(downsampled) / len(downsampled) if downsampled else 0.0

    return {
        "downsampled": downsampled,
        "anomaly_indices": anomaly_indices,
        "summary_mean": round(summary_mean, 4),
    }


def correlate_streams(
    stream_a: List[float], stream_b: List[float], max_lag: int = 5,
) -> dict:
    """Cross-correlate two telemetry streams to find optimal time offset."""
    if not stream_a or not stream_b:
        return {"best_lag": 0, "correlation": 0.0}

    n = min(len(stream_a), len(stream_b))
    best_lag = 0
    best_corr = -float("inf")

    for lag in range(-max_lag, max_lag + 1):
        total = 0.0
        count = 0
        for i in range(n):
            j = i + lag
            if 0 <= j < len(stream_b) - 1:
                total += stream_a[i] * stream_b[j]
                count += 1
        if count > 0:
            corr = total / count
            if corr > best_corr:
                best_corr = corr
                best_lag = lag

    return {"best_lag": best_lag, "correlation": round(best_corr, 4)}


def adaptive_threshold(
    values: List[float], sensitivity: float = 1.5, min_samples: int = 10,
) -> dict:
    """Compute adaptive anomaly detection threshold from recent telemetry."""
    if len(values) < min_samples:
        return {"threshold": float("inf"), "baseline": 0.0, "std": 0.0, "ready": False}

    recent = values[-min_samples:]
    baseline = sum(recent) / len(recent)
    var = sum((v - baseline) ** 2 for v in recent) / len(recent)
    std = sqrt(var) if var > 0 else 0.001
    threshold = baseline + (sensitivity ** 2) * std

    return {
        "threshold": round(threshold, 4),
        "baseline": round(baseline, 4),
        "std": round(std, 4),
        "ready": True,
    }


def telemetry_health_check(
    values: List[float], sensitivity: float = 1.5, min_samples: int = 10,
) -> dict:
    """Combined telemetry health assessment using adaptive thresholds."""
    thresh_info = adaptive_threshold(values, sensitivity, min_samples)
    if not thresh_info["ready"]:
        return {"status": "insufficient_data", "anomalies": 0, "threshold": 0.0}

    threshold = thresh_info["threshold"]
    anomalies = sum(1 for v in values if v > threshold)
    status = "healthy" if anomalies < 3 else "degraded"

    return {
        "status": status,
        "anomalies": anomalies,
        "threshold": threshold,
    }


def align_telemetry_timestamps(
    readings: List[dict], reference_time, max_drift_s: float = 60.0,
) -> List[dict]:
    """Align telemetry readings to a reference timestamp, flagging drift."""
    if not readings:
        return []
    aligned: List[dict] = []
    prev_offset = 0.0
    for reading in readings:
        ts = reading.get("timestamp")
        if ts is None:
            aligned.append({**reading, "offset_s": 0.0, "aligned": True})
            continue
        offset = (ts - reference_time).total_seconds()
        drift = abs(offset - prev_offset)
        prev_offset = offset
        aligned.append({
            **reading,
            "offset_s": round(offset, 4),
            "aligned": drift <= max_drift_s,
        })
    return aligned
