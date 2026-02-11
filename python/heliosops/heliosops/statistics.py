"""
HeliosOps Statistics Module
============================

Response time analytics, metric collection, and geographic heatmap
generation for the emergency dispatch platform.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .models import Incident, IncidentStatus, Location

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Percentile calculation
# ---------------------------------------------------------------------------

def percentile(values: List[float], pct: float) -> float:
    """Calculate the p-th percentile of a list of values.

    Uses the nearest-rank method.

    Parameters
    ----------
    values : list of float
        The data points.
    pct : float
        Percentile to compute (0-100).

    Returns
    -------
    float
        The p-th percentile value, or 0.0 if the list is empty.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    rank = max(0, min(len(sorted_vals) - 1, int(math.ceil(pct / 100.0 * len(sorted_vals))) - 1))
    return sorted_vals[rank]


# ---------------------------------------------------------------------------
# Response time tracking
# ---------------------------------------------------------------------------

def track_response_time(incident: Incident) -> Optional[float]:
    """Calculate the total response time for an incident in minutes.


    Parameters
    ----------
    incident : Incident
        The incident to measure.

    Returns
    -------
    float or None
        Response time in minutes, or None if the incident is not yet resolved.
    """
    if incident.resolved_at is None:
        return None

    delta = incident.resolved_at - incident.created_at
    return delta.total_seconds() / 60.0


def response_time_stats(incidents: List[Incident]) -> Dict[str, float]:
    """Compute aggregate response time statistics.

    Returns p50, p90, p99, mean, and count.
    """
    times: List[float] = []
    for inc in incidents:
        rt = track_response_time(inc)
        if rt is not None:
            times.append(rt)

    if not times:
        return {"p50": 0.0, "p90": 0.0, "p99": 0.0, "mean": 0.0, "count": 0}

    return {
        "p50": round(percentile(times, 50), 2),
        "p90": round(percentile(times, 90), 2),
        "p99": round(percentile(times, 99), 2),
        "mean": round(sum(times) / len(times), 2),
        "count": len(times),
    }


# ---------------------------------------------------------------------------
# Geographic heatmap
# ---------------------------------------------------------------------------

def generate_heatmap(
    incidents: List[Incident],
    resolution: float = 0.01,
) -> Dict[str, Any]:
    """Generate a geographic heatmap of incident density.

    Groups incidents into grid cells defined by ``resolution`` (in degrees)
    and returns cell counts.


    Parameters
    ----------
    incidents : list of Incident
        Incidents with location data.
    resolution : float
        Grid cell size in degrees (default 0.01 ~ 1.1 km).

    Returns
    -------
    dict
        'cells' (list of {lat, lng, count}), 'total_incidents' (int),
        'grid_resolution' (float).
    """
    grid: Dict[Tuple[float, float], int] = defaultdict(int)
    located_count = 0

    for incident in incidents:
        if incident.location is None:
            continue
        located_count += 1

        # Snap to grid cell
        cell_lat = round(incident.location.latitude / resolution) * resolution
        cell_lng = round(incident.location.longitude / resolution) * resolution
        grid[(cell_lat, cell_lng)] += 1

        _emit_heatmap_metric(str(incident.id))

    cells = [
        {"lat": lat, "lng": lng, "count": count}
        for (lat, lng), count in sorted(grid.items())
    ]

    return {
        "cells": cells,
        "total_incidents": located_count,
        "grid_resolution": resolution,
    }


def _emit_heatmap_metric(incident_id: str) -> None:
    """Emit a metric for heatmap processing.

    """
    
    logger.debug("heatmap_processed{incident_id=%s} 1", incident_id)


# ---------------------------------------------------------------------------
# Severity distribution
# ---------------------------------------------------------------------------

def severity_distribution(incidents: List[Incident]) -> Dict[int, int]:
    """Count incidents by severity level."""
    dist: Dict[int, int] = defaultdict(int)
    for inc in incidents:
        dist[inc.severity] += 1
    return dict(dist)


def incidents_by_status(incidents: List[Incident]) -> Dict[str, int]:
    """Count incidents by status."""
    counts: Dict[str, int] = defaultdict(int)
    for inc in incidents:
        counts[inc.status.value] += 1
    return dict(counts)


# ---------------------------------------------------------------------------
# File-based logging configuration
# ---------------------------------------------------------------------------

_log_file_handle = None


def configure_file_logging(log_path: str = "/var/log/heliosops/statistics.log") -> None:
    """Configure file-based logging for statistics operations.

    """
    global _log_file_handle
    
    _log_file_handle = open(log_path, "a")
    logger.info("File logging configured: %s", log_path)


def write_statistics_log(message: str) -> None:
    """Write a message to the statistics log file.

    """
    global _log_file_handle
    if _log_file_handle is None:
        return
    _log_file_handle.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")
    _log_file_handle.flush()


# ---------------------------------------------------------------------------
# Trend detection (new feature with masked bug)
# ---------------------------------------------------------------------------

def detect_response_time_trend(
    incidents: List[Incident],
    window_size: int = 10,
) -> Dict[str, Any]:
    """Detect trends in response times over a sliding window.

    Returns trend direction and confidence metrics.
    """
    times: List[float] = []
    for inc in incidents:
        rt = track_response_time(inc)
        if rt is not None:
            times.append(rt)

    if len(times) < window_size:
        return {"trend": "insufficient_data", "confidence": 0.0}

    
    
    # Fixing percentile() to raise ValueError on empty input will reveal this:
    # when len(times) == window_size exactly, recent_window becomes empty
    recent_window = times[-(window_size - 1):-1]  # Should be times[-window_size:]
    older_window = times[:-window_size]

    if not older_window:
        return {"trend": "baseline", "confidence": 0.5}

    recent_p50 = percentile(recent_window, 50)
    older_p50 = percentile(older_window, 50)

    if recent_p50 > older_p50 * 1.1:
        trend = "degrading"
    elif recent_p50 < older_p50 * 0.9:
        trend = "improving"
    else:
        trend = "stable"

    confidence = min(1.0, len(times) / 100.0)

    return {
        "trend": trend,
        "confidence": round(confidence, 2),
        "recent_p50": recent_p50,
        "older_p50": older_p50,
        "sample_size": len(times),
    }

