"""
SynapseNet Monitoring Service
Terminal Bench v2 - Model Monitoring & Drift Detection (FastAPI)

Contains bugs:
- M3: Batch normalization statistics leak (via shared.ml)
- M4: Feature drift detection false positive (via shared.ml)
- J5: Error aggregation groups wrong
- J6: Inference latency histogram bucket overflow
"""
import os
import time
import logging
import math
from typing import Dict, Any, Optional, List
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ErrorAggregator:
    """
    Aggregate errors for alerting.

    BUG J5: Groups errors by message string instead of error type/code.
    Similar errors with different parameters are treated as separate groups,
    causing too many alert groups and missed patterns.
    """

    def __init__(self):
        self._error_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def record_error(self, error: Dict[str, Any]):
        """
        Record an error for aggregation.

        BUG J5: Groups by full error message instead of error type.
        """
        
        group_key = error.get("message", "unknown")  # Should use error.get("type", "unknown")
        self._error_groups[group_key].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": error,
        })

    def get_groups(self) -> Dict[str, int]:
        """Get error groups with counts."""
        return {k: len(v) for k, v in self._error_groups.items()}

    def get_top_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top error groups by count."""
        sorted_groups = sorted(self._error_groups.items(), key=lambda x: len(x[1]), reverse=True)
        return [{"group": k, "count": len(v)} for k, v in sorted_groups[:limit]]


class LatencyHistogram:
    """
    Histogram for tracking inference latencies.

    BUG J6: Bucket boundaries use fixed sizes that overflow for very
    large latencies. Latencies > 10s are placed in the wrong bucket.
    """

    def __init__(self, buckets: Optional[List[float]] = None):
        
        self.buckets = buckets or [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
        
        self._counts: Dict[float, int] = {b: 0 for b in self.buckets}
        self._sum = 0.0
        self._count = 0

    def observe(self, value: float):
        """
        Record a latency observation.

        BUG J6: Values larger than max bucket are silently dropped.
        """
        self._count += 1
        self._sum += value

        placed = False
        for bucket in self.buckets:
            if value <= bucket:
                self._counts[bucket] += 1
                placed = True
                break

        
        if not placed:
            pass  # Should have +Inf bucket

    def get_percentile(self, percentile: float) -> float:
        """Get approximate percentile from histogram."""
        target_count = self._count * percentile / 100.0
        cumulative = 0
        for bucket in sorted(self.buckets):
            cumulative += self._counts[bucket]
            if cumulative >= target_count:
                return bucket
        return self.buckets[-1] if self.buckets else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get histogram statistics."""
        return {
            "count": self._count,
            "sum": self._sum,
            "avg": self._sum / max(self._count, 1),
            "p50": self.get_percentile(50),
            "p95": self.get_percentile(95),
            "p99": self.get_percentile(99),
        }


class ModelMonitor:
    """Monitor model performance and data drift."""

    def __init__(self):
        self.error_aggregator = ErrorAggregator()
        self.latency_histogram = LatencyHistogram()
        self._model_metrics: Dict[str, Dict[str, Any]] = {}

    def record_prediction(self, model_id: str, latency: float, success: bool):
        """Record a prediction event."""
        self.latency_histogram.observe(latency)
        if model_id not in self._model_metrics:
            self._model_metrics[model_id] = {
                "total_predictions": 0,
                "successful_predictions": 0,
                "failed_predictions": 0,
            }
        self._model_metrics[model_id]["total_predictions"] += 1
        if success:
            self._model_metrics[model_id]["successful_predictions"] += 1
        else:
            self._model_metrics[model_id]["failed_predictions"] += 1

    def get_model_health(self, model_id: str) -> Dict[str, Any]:
        """Get model health metrics."""
        metrics = self._model_metrics.get(model_id, {})
        total = metrics.get("total_predictions", 0)
        success = metrics.get("successful_predictions", 0)
        return {
            "model_id": model_id,
            "total_predictions": total,
            "success_rate": success / max(total, 1),
            "latency_stats": self.latency_histogram.get_stats(),
        }


class AlertThrottler:
    """Throttle alerts to prevent alert fatigue."""

    def __init__(self, window_seconds: float = 300.0, max_alerts_per_window: int = 5):
        self.window_seconds = window_seconds
        self.max_alerts_per_window = max_alerts_per_window
        self._alert_history: Dict[str, List[float]] = {}

    def should_alert(self, alert_key: str) -> bool:
        """Determine if an alert should be sent based on throttle rules."""
        now = time.time()

        if alert_key not in self._alert_history:
            self._alert_history[alert_key] = [now]
            return True

        history = self._alert_history[alert_key]
        recent = [t for t in history if now - t < self.window_seconds]
        self._alert_history[alert_key] = recent

        if len(recent) < self.max_alerts_per_window:
            self._alert_history[alert_key].append(now)
            return True

        return False

    def get_throttled_count(self, alert_key: str) -> int:
        """Get how many alerts were throttled for a key."""
        history = self._alert_history.get(alert_key, [])
        now = time.time()
        recent = [t for t in history if now - t < self.window_seconds]
        return max(0, len(recent) - self.max_alerts_per_window)


class AnomalyDetector:
    """Simple anomaly detection using rolling statistics."""

    def __init__(self, window_size: int = 100, sigma_threshold: float = 3.0):
        self.window_size = window_size
        self.sigma_threshold = sigma_threshold
        self._values: Dict[str, List[float]] = {}

    def observe(self, metric_name: str, value: float) -> bool:
        """Record a value and return True if it's anomalous."""
        if metric_name not in self._values:
            self._values[metric_name] = []

        history = self._values[metric_name]

        if len(history) < 10:
            history.append(value)
            return False

        mean = sum(history[-self.window_size:]) / len(history[-self.window_size:])
        variance = sum((x - mean) ** 2 for x in history[-self.window_size:]) / len(history[-self.window_size:])
        std = variance ** 0.5

        history.append(value)
        if len(history) > self.window_size * 2:
            self._values[metric_name] = history[-self.window_size * 2:]

        if std < 1e-10:
            return False

        z_score = abs(value - mean) / std
        return z_score > self.sigma_threshold

    def get_baseline(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get the baseline statistics for a metric."""
        history = self._values.get(metric_name, [])
        if len(history) < 2:
            return None
        recent = history[-self.window_size:]
        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)
        return {"mean": mean, "std": variance ** 0.5, "count": len(recent)}


class SLOTracker:
    """Track Service Level Objectives."""

    def __init__(self):
        self._slos: Dict[str, Dict[str, Any]] = {}
        self._measurements: Dict[str, List[Dict[str, Any]]] = {}

    def define_slo(self, name: str, target: float, window_seconds: float = 3600.0):
        """Define an SLO target."""
        self._slos[name] = {"target": target, "window": window_seconds}
        self._measurements[name] = []

    def record(self, slo_name: str, value: float, is_good: bool):
        """Record a measurement against an SLO."""
        if slo_name not in self._slos:
            return
        self._measurements[slo_name].append({
            "value": value,
            "is_good": is_good,
            "timestamp": time.time(),
        })

    def get_slo_status(self, slo_name: str) -> Dict[str, Any]:
        """Get current SLO compliance status."""
        if slo_name not in self._slos:
            return {"error": "SLO not found"}

        slo = self._slos[slo_name]
        now = time.time()
        window_start = now - slo["window"]

        recent = [m for m in self._measurements.get(slo_name, [])
                  if m["timestamp"] >= window_start]

        if not recent:
            return {"slo": slo_name, "compliance": 1.0, "target": slo["target"],
                    "total": 0, "good": 0}

        good_count = sum(1 for m in recent if m["is_good"])
        compliance = good_count / len(recent)

        return {
            "slo": slo_name,
            "compliance": compliance,
            "target": slo["target"],
            "total": len(recent),
            "good": good_count,
            "meeting_target": compliance >= slo["target"],
            "error_budget_remaining": max(0, compliance - slo["target"]) / max(slo["target"], 1e-10),
        }


monitor = ModelMonitor()

app = {
    "service": "monitoring",
    "port": 8009,
    "monitor": monitor,
}
