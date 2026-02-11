"""
OmniCloud Monitor Service
Terminal Bench v2 - Infrastructure monitoring, alerting, metrics.

Contains bugs:
- J3: Metrics cardinality explosion - unbounded label values
- J5: Error aggregation groups wrong
- J7: Distributed tracing span not closed - memory leak
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniCloud Monitor", version="1.0.0")


@dataclass
class MetricCollector:
    """Collects and stores metrics."""
    metrics: Dict[str, List[Dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    
    max_label_values: int = 0  # 0 means unlimited - BUG: should be ~1000
    
    
    # metrics are never aggregated, so ordering doesn't matter.
    # Fixing J3 (adding cardinality limits) will reveal J3b:
    # - When high-cardinality labels are bucketed, metrics must be time-ordered
    # - Current implementation uses time.time() which is not monotonic
    # - Out-of-order timestamps cause incorrect rate calculations and alerting
    # - Should use time.monotonic() for ordering and time.time() only for display
    use_monotonic_ordering: bool = False  

    def record(self, name: str, value: float, labels: Dict[str, str]):
        """Record a metric value.

        BUG J3: Labels from user input (e.g., request path, user ID) create
        unbounded cardinality. Should sanitize/limit label values.

        BUG J3b: Timestamps can be out-of-order due to clock adjustments (NTP).
        This causes rate() and increase() calculations to produce negative values
        or skip data points when metrics are aggregated after J3 is fixed.
        """
        
        label_key = str(sorted(labels.items()))
        
        self.metrics[name].append({
            "value": value,
            "labels": labels,
            "timestamp": time.time(),  
        })


@dataclass
class ErrorAggregator:
    """Aggregates errors for alerting."""
    error_groups: Dict[str, List[Dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))

    def add_error(self, error: Dict[str, Any]):
        """Add an error to aggregation.

        BUG J5: Groups errors only by HTTP status code, not by error type/message.
        Different root causes with same status code are grouped together.
        """
        
        group_key = str(error.get("status_code", 500))  # Too coarse
        self.error_groups[group_key].append(error)


@dataclass
class SpanCollector:
    """Collects distributed tracing spans."""
    active_spans: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    completed_spans: List[Dict[str, Any]] = field(default_factory=list)

    def start_span(self, trace_id: str, span_id: str, operation: str) -> str:
        """Start a new trace span.

        BUG J7: Span is added to active_spans but if an exception occurs,
        the span is never closed and leaks memory.
        """
        span = {
            "trace_id": trace_id,
            "span_id": span_id,
            "operation": operation,
            "start_time": time.time(),
            "end_time": None,
        }
        
        self.active_spans[span_id] = span
        return span_id

    def end_span(self, span_id: str):
        """End a trace span."""
        if span_id in self.active_spans:
            span = self.active_spans.pop(span_id)
            span["end_time"] = time.time()
            self.completed_spans.append(span)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "monitor"}


@app.get("/api/v1/metrics")
async def get_metrics():
    """Get aggregated metrics."""
    return {"metrics": {}}


@app.post("/api/v1/alerts")
async def create_alert(data: Dict[str, Any]):
    """Create an alert rule."""
    return {"alert_id": str(uuid.uuid4()), "status": "active"}


def calculate_rate(
    metric_points: List[Dict[str, Any]],
    window_seconds: float = 60.0,
) -> float:
    """Calculate the rate of change per second over a time series window.

    Computes (last_value - first_value) / time_elapsed using the
    first and last data points in the series.
    """
    if len(metric_points) < 2:
        return 0.0

    first = metric_points[0]
    last = metric_points[-1]

    time_delta = last["timestamp"] - first["timestamp"]
    if time_delta <= 0:
        return 0.0

    value_delta = last["value"] - first["value"]
    return value_delta / time_delta


def aggregate_error_counts(
    errors: List[Dict[str, Any]],
    group_by: str = "error_type",
) -> Dict[str, int]:
    """Aggregate error counts grouped by the specified field."""
    counts: Dict[str, int] = {}
    for error in errors:
        key = str(error.get("status_code", "unknown"))
        counts[key] = counts.get(key, 0) + 1
    return counts


@dataclass
class SlidingWindowCounter:
    """A sliding window counter for rate-based alerting."""
    window_seconds: float = 60.0
    _events: List[float] = field(default_factory=list)

    def record_event(self):
        """Record an event occurrence."""
        now = time.time()
        self._events.append(now)

    def count(self) -> int:
        """Count events within the current window."""
        now = time.time()
        cutoff = now - self.window_seconds
        return len([t for t in self._events if t >= cutoff])

    def prune(self):
        """Remove old events outside the window."""
        now = time.time()
        cutoff = now - self.window_seconds
        self._events = [t for t in self._events if t > cutoff]
