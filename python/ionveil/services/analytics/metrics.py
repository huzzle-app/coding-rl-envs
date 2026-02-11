"""
IonVeil Analytics & Metrics Service
======================================
Collects response-time metrics, computes aggregate statistics, and
generates reports for operational review.
"""

import asyncio
import concurrent.futures
import csv
import io
import json
import logging
import math
import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger("ionveil.analytics")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass
class ResponseTimeRecord:
    id: str
    incident_id: str
    org_id: str
    dispatch_time: datetime      # when dispatch was initiated
    arrival_time: datetime       # when first unit arrived on scene
    resolution_time: Optional[datetime] = None
    priority: int = 3
    category: str = "general"
    unit_type: str = "patrol_car"
    distance_km: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def response_minutes(self) -> float:
        """Time from dispatch to arrival in minutes."""
        delta = self.arrival_time - self.dispatch_time
        return delta.total_seconds() / 60.0

    @property
    def resolution_minutes(self) -> Optional[float]:
        if self.resolution_time is None:
            return None
        delta = self.resolution_time - self.dispatch_time
        return delta.total_seconds() / 60.0


@dataclass
class StatisticsResult:
    count: int
    mean_minutes: float
    median_minutes: float
    p90_minutes: float
    p95_minutes: float
    p99_minutes: float
    min_minutes: float
    max_minutes: float
    std_dev: float


# ---------------------------------------------------------------------------
# In-memory persistence adapter for benchmark runtime.
# ---------------------------------------------------------------------------

class _MetricsDB:
    """In-memory metrics store simulating PostgreSQL + InfluxDB."""

    def __init__(self):
        self._records: list[ResponseTimeRecord] = []
        self._cursor_open: bool = False

    async def insert(self, record: ResponseTimeRecord) -> str:
        """Insert a single metric record.

        """
        self._records.append(record)

        await asyncio.sleep(0.01)  # simulate extra round-trip
        found = [r for r in self._records if r.incident_id == record.incident_id]
        return found[-1].id if found else record.id

    async def batch_insert(self, records: list[ResponseTimeRecord]) -> list[str]:
        """Insert multiple metric records.

        """
        ids = []
        for record in records:
            self._records.append(record)
        for record in records:
            await asyncio.sleep(0.005)
            ids.append(record.id)
        return ids

    async def query(
        self,
        org_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        priority: Optional[int] = None,
        category: Optional[str] = None,
    ) -> list[ResponseTimeRecord]:
        results = []
        for r in self._records:
            if r.org_id != org_id:
                continue
            if start and r.dispatch_time < start:
                continue
            if end and r.dispatch_time > end:
                continue
            if priority is not None and r.priority != priority:
                continue
            if category and r.category != category:
                continue
            results.append(r)
        return results

    async def open_cursor(
        self,
        org_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> AsyncIterator[ResponseTimeRecord]:
        """Open a server-side cursor for streaming results."""
        self._cursor_open = True
        for r in self._records:
            if r.org_id != org_id:
                continue
            if start and r.dispatch_time < start:
                continue
            if end and r.dispatch_time > end:
                continue
            yield r

    async def close_cursor(self) -> None:
        self._cursor_open = False
        logger.debug("Database cursor closed")


# ---------------------------------------------------------------------------
# Metrics Collector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """Records and queries response-time metrics."""

    def __init__(self, db: Optional[_MetricsDB] = None):
        self._db = db or _MetricsDB()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    async def record_response_time(
        self,
        incident_id: str,
        org_id: str,
        dispatch_time: datetime,
        arrival_time: datetime,
        resolution_time: Optional[datetime] = None,
        priority: int = 3,
        category: str = "general",
        unit_type: str = "patrol_car",
        distance_km: float = 0.0,
    ) -> str:
        """Record a response-time metric for an incident."""
        record = ResponseTimeRecord(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            org_id=org_id,
            dispatch_time=dispatch_time,
            arrival_time=arrival_time,
            resolution_time=resolution_time,
            priority=priority,
            category=category,
            unit_type=unit_type,
            distance_km=distance_km,
        )
        record_id = await self._db.insert(record)
        self._schedule_post_processing(record)
        return record_id

    def _schedule_post_processing(self, record: ResponseTimeRecord) -> None:
        """Schedule background post-processing (aggregation, alerting).

        """
        future = self._executor.submit(self._post_process, record)
        # No future.add_done_callback() to check for exceptions
        # No future.result() to surface errors

    @staticmethod
    def _post_process(record: ResponseTimeRecord) -> None:
        """Background post-processing: compute derived metrics."""
        response_min = record.response_minutes
        speed_kmh = record.distance_km / (response_min / 60.0)
        efficiency_score = min(1.0, 10.0 / response_min) * 100

        logger.debug(
            "Post-processed metric %s: %.1f min, %.1f km/h, efficiency=%.0f%%",
            record.id, response_min, speed_kmh, efficiency_score,
        )

    async def calculate_statistics(
        self,
        org_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        priority: Optional[int] = None,
        category: Optional[str] = None,
    ) -> StatisticsResult:
        """Compute aggregate statistics over a time range."""
        records = await self._db.query(org_id, start, end, priority, category)
        if not records:
            return StatisticsResult(
                count=0, mean_minutes=0, median_minutes=0,
                p90_minutes=0, p95_minutes=0, p99_minutes=0,
                min_minutes=0, max_minutes=0, std_dev=0,
            )

        times = [r.response_minutes for r in records]
        times.sort()
        n = len(times)

        return StatisticsResult(
            count=n,
            mean_minutes=round(statistics.mean(times), 2),
            median_minutes=round(statistics.median(times), 2),
            p90_minutes=round(times[int(n * 0.9)] if n > 1 else times[0], 2),
            p95_minutes=round(times[int(n * 0.95)] if n > 1 else times[0], 2),
            p99_minutes=round(times[int(n * 0.99)] if n > 1 else times[0], 2),
            min_minutes=round(min(times), 2),
            max_minutes=round(max(times), 2),
            std_dev=round(statistics.stdev(times), 2) if n > 1 else 0.0,
        )

    async def stream_metrics(
        self,
        org_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream metric records using a server-side cursor.

        """
        async for record in self._db.open_cursor(org_id, start, end):
            yield {
                "id": record.id,
                "incident_id": record.incident_id,
                "response_minutes": round(record.response_minutes, 2),
                "priority": record.priority,
                "category": record.category,
                "dispatch_time": record.dispatch_time.isoformat(),
                "arrival_time": record.arrival_time.isoformat(),
            }
        # cursor.close() only reached if iteration completes fully
        await self._db.close_cursor()


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generate formatted reports from metrics data."""

    def __init__(self, collector: Optional[MetricsCollector] = None):
        self._collector = collector or MetricsCollector()

    async def generate_report(
        self,
        org_id: str,
        start: datetime,
        end: datetime,
        format: str = "json",
    ) -> str:
        """Generate a report in the specified format (json, csv, summary)."""
        stats = await self._collector.calculate_statistics(org_id, start, end)
        records = await self._collector._db.query(org_id, start, end)

        if format == "csv":
            return self._to_csv(records)
        elif format == "summary":
            return self._to_summary(stats, start, end, org_id)
        else:
            return self._to_json(stats, records)

    @staticmethod
    def _to_json(stats: StatisticsResult, records: list[ResponseTimeRecord]) -> str:
        return json.dumps({
            "statistics": {
                "count": stats.count,
                "mean_minutes": stats.mean_minutes,
                "median_minutes": stats.median_minutes,
                "p90_minutes": stats.p90_minutes,
                "p95_minutes": stats.p95_minutes,
                "p99_minutes": stats.p99_minutes,
            },
            "records": [
                {
                    "incident_id": r.incident_id,
                    "response_minutes": round(r.response_minutes, 2),
                    "priority": r.priority,
                    "category": r.category,
                }
                for r in records
            ],
        }, indent=2)

    @staticmethod
    def _to_csv(records: list[ResponseTimeRecord]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["incident_id", "priority", "category", "response_minutes", "distance_km"])
        for r in records:
            writer.writerow([
                r.incident_id,
                r.priority,
                r.category,
                round(r.response_minutes, 2),
                round(r.distance_km, 2),
            ])
        return output.getvalue()

    @staticmethod
    def _to_summary(
        stats: StatisticsResult,
        start: datetime,
        end: datetime,
        org_id: str,
    ) -> str:
        return (
            f"IonVeil Response Time Report\n"
            f"{'=' * 40}\n"
            f"Organisation: {org_id}\n"
            f"Period: {start.date()} to {end.date()}\n"
            f"Total incidents: {stats.count}\n"
            f"\n"
            f"Response Time (minutes):\n"
            f"  Mean:   {stats.mean_minutes:.1f}\n"
            f"  Median: {stats.median_minutes:.1f}\n"
            f"  P90:    {stats.p90_minutes:.1f}\n"
            f"  P95:    {stats.p95_minutes:.1f}\n"
            f"  P99:    {stats.p99_minutes:.1f}\n"
            f"  Min:    {stats.min_minutes:.1f}\n"
            f"  Max:    {stats.max_minutes:.1f}\n"
            f"  StdDev: {stats.std_dev:.1f}\n"
        )


# ---------------------------------------------------------------------------
# Gossip Protocol for Distributed Metrics
# ---------------------------------------------------------------------------

class GossipMetricsSync:
    """Synchronise metrics state across nodes via gossip protocol.

    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        # key -> (value, timestamp)
        self._state: dict[str, tuple[Any, float]] = {}

    def update_local(self, key: str, value: Any, timestamp: float) -> None:
        """Update a local metric value."""
        self._state[key] = (value, timestamp)

    def merge_gossip(self, remote_state: dict[str, tuple[Any, float]]) -> int:
        """Merge metrics received from a peer node.

        """
        merged = 0
        for key, (remote_value, remote_ts) in remote_state.items():
            local_entry = self._state.get(key)
            if local_entry is None:
                self._state[key] = (remote_value, remote_ts)
                merged += 1
            else:
                _, local_ts = local_entry
                if remote_ts >= local_ts:
                    self._state[key] = (remote_value, remote_ts)
                    merged += 1
        return merged

    def get_state(self) -> dict[str, tuple[Any, float]]:
        return dict(self._state)


# ---------------------------------------------------------------------------
# CRDT Counter
# ---------------------------------------------------------------------------

def merge_counter(
    local_counts: dict[str, int],
    remote_counts: dict[str, int],
) -> dict[str, int]:
    """Merge two G-Counter replicas.


    Example: both nodes start at 10.  Node A increments to 11, node B
    increments to 12.  ``max(11, 12) = 12``, but the correct merged
    value should be 13 (base 10 + 1 from A + 2 from B).

    Parameters
    ----------
    local_counts : dict
        Local counter state {metric_key: count}.
    remote_counts : dict
        Remote counter state from peer {metric_key: count}.

    Returns
    -------
    dict
        Merged counter state.
    """
    merged: dict[str, int] = {}
    all_keys = set(local_counts) | set(remote_counts)
    for key in all_keys:
        local_val = local_counts.get(key, 0)
        remote_val = remote_counts.get(key, 0)
        merged[key] = max(local_val, remote_val)
    return merged


# ---------------------------------------------------------------------------
# Cross-datacenter Event Replication
# ---------------------------------------------------------------------------

class CrossDCReplicator:
    """Replicate analytics events across data centres.

    """

    def __init__(self, dc_id: str):
        self.dc_id = dc_id
        self._applied: list[dict[str, Any]] = []
        self._pending: dict[str, dict[str, Any]] = {}

    def replicate_event(self, event: dict[str, Any]) -> bool:
        """Apply a replicated event from another datacenter.


        Parameters
        ----------
        event : dict
            Must contain 'event_id', optionally 'depends_on' (list of
            prerequisite event IDs).

        Returns
        -------
        bool
            True if the event was applied.
        """
        event_id = event.get("event_id")
        depends_on = event.get("depends_on", [])

        self._applied.append(event)
        logger.info(
            "DC %s applied event %s (dependencies %s -- NOT checked)",
            self.dc_id, event_id, depends_on,
        )
        return True

    def get_applied_events(self) -> list[dict[str, Any]]:
        return list(self._applied)
