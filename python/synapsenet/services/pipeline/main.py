"""
SynapseNet Pipeline Service
Terminal Bench v2 - Data Pipeline Orchestration (Celery/FastAPI)

Contains bugs:
- D1: Data validation schema mismatch
- D3: Backfill duplicate processing
- D4: Late-arriving data window close
- D5: Partition key distribution skew
- D8: Pipeline DAG cycle detection missing
"""
import os
import time
import uuid
import hashlib
import logging
from typing import Dict, Any, Optional, List, Set
from collections import defaultdict
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class DataValidator:
    """
    Validate incoming data against expected schemas.

    BUG D1: Schema validation compares against producer schema version,
    but consumer may have a different (newer or older) version.
    """

    def __init__(self):
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register_schema(self, name: str, version: int, schema: Dict[str, Any]):
        """Register a data schema."""
        self._schemas[f"{name}:v{version}"] = schema

    def validate(self, data: Dict[str, Any], schema_name: str, version: int = 1) -> bool:
        """
        Validate data against schema.

        BUG D1: Always validates against version 1 even when version param differs.
        """
        
        key = f"{schema_name}:v1"  # Should be f"{schema_name}:v{version}"
        schema = self._schemas.get(key)
        if not schema:
            return True  # No schema = no validation (also a bug)

        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                return False
        return True


class BackfillProcessor:
    """
    Process data backfills.

    BUG D3: Does not track processed records. On restart or retry,
    the same records are processed again, causing duplicates.
    """

    def __init__(self):
        self._processed_ids: Set[str] = set()

    def process_record(self, record_id: str, data: Dict[str, Any]) -> bool:
        """
        Process a backfill record.

        BUG D3: Processed IDs are tracked in memory but lost on restart.
        Also, the dedup check uses wrong field.
        """
        
        if record_id in self._processed_ids:
            return False  # Already processed

        # Process the record
        result = self._transform(data)

        
        self._processed_ids.add(record_id)
        return True

    def _transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a record."""
        return {k: v for k, v in data.items()}


class WindowProcessor:
    """
    Time-window based data processing.

    BUG D4: Window close is too aggressive - late-arriving data
    that falls within the allowed lateness window is still rejected.
    """

    def __init__(self, window_size: timedelta = timedelta(minutes=5), allowed_lateness: timedelta = timedelta(minutes=1)):
        self.window_size = window_size
        self.allowed_lateness = allowed_lateness
        self._windows: Dict[str, Dict[str, Any]] = {}
        self._closed_windows: Set[str] = set()

    def process_event(self, event_time: datetime, data: Dict[str, Any]) -> bool:
        """
        Process an event into the appropriate window.

        BUG D4: Rejects late-arriving data even when within allowed lateness.
        """
        window_key = self._get_window_key(event_time)
        now = datetime.now(timezone.utc)

        if window_key in self._closed_windows:
            
            # Should check: if now - window_end < self.allowed_lateness: accept
            return False  # Rejected as late

        if window_key not in self._windows:
            self._windows[window_key] = {"events": [], "created_at": now}

        self._windows[window_key]["events"].append(data)
        return True

    def _get_window_key(self, event_time: datetime) -> str:
        """Get the window key for an event time."""
        window_start = event_time.replace(
            minute=(event_time.minute // 5) * 5,
            second=0,
            microsecond=0,
        )
        return window_start.isoformat()

    def close_window(self, window_key: str):
        """Close a window."""
        self._closed_windows.add(window_key)


class PartitionRouter:
    """
    Route data to partitions.

    BUG D5: Partition key hashing produces skewed distribution.
    Some partitions receive significantly more data than others.
    """

    def __init__(self, num_partitions: int = 8):
        self.num_partitions = num_partitions

    def route(self, partition_key: str) -> int:
        """
        Route to a partition based on key.

        BUG D5: Uses len() of key instead of hash, causing skew.
        """
        
        return len(partition_key) % self.num_partitions  # Should use hash


class PipelineDAG:
    """
    Pipeline directed acyclic graph.

    BUG D8: No cycle detection when adding edges. A cycle in the pipeline
    causes infinite execution.
    """

    def __init__(self):
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: Dict[str, List[str]] = defaultdict(list)

    def add_node(self, node_id: str, transform_fn=None):
        """Add a processing node."""
        self._nodes[node_id] = {"fn": transform_fn, "status": "idle"}

    def add_edge(self, from_node: str, to_node: str) -> bool:
        """
        Add an edge between nodes.

        BUG D8: Does not check if adding this edge creates a cycle.
        """
        
        self._edges[from_node].append(to_node)
        return True

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the pipeline.

        BUG D8: If there's a cycle, this will loop forever.
        """
        executed = set()
        result = dict(input_data)

        def execute_node(node_id, depth=0):
            if depth > 100:  # Safety limit, but too high
                raise RecursionError(f"Pipeline execution exceeded depth limit at {node_id}")
            if node_id in executed:
                return
            
            for dep in self._edges.get(node_id, []):
                execute_node(dep, depth + 1)
            executed.add(node_id)

        for node_id in self._nodes:
            execute_node(node_id)

        return result


class PipelineStateMachine:
    """Track pipeline execution lifecycle."""

    VALID_STATES = {"idle", "validating", "queued", "running", "paused",
                    "checkpointing", "completed", "failed", "cancelled"}

    TRANSITIONS = {
        "idle": {"validating", "cancelled"},
        "validating": {"queued", "failed"},
        "queued": {"running", "cancelled"},
        "running": {"paused", "checkpointing", "completed", "failed"},
        "paused": {"running", "cancelled", "completed"},
        "checkpointing": {"running", "failed"},
        "completed": {"idle"},
        "failed": {"idle", "validating"},
        "cancelled": {"idle"},
    }

    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self.state = "idle"
        self._history = [{"state": "idle", "timestamp": time.time()}]
        self._checkpoint_data = None

    def transition(self, new_state: str) -> bool:
        """Attempt state transition."""
        if new_state not in self.VALID_STATES:
            return False
        allowed = self.TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            return False
        self.state = new_state
        self._history.append({"state": new_state, "timestamp": time.time()})
        return True

    def get_state(self) -> str:
        return self.state

    def save_checkpoint(self, data: Any) -> bool:
        """Save pipeline checkpoint during execution."""
        if self.state != "checkpointing":
            return False
        self._checkpoint_data = data
        return True

    def restore_checkpoint(self) -> Optional[Any]:
        """Restore from last checkpoint."""
        return self._checkpoint_data

    def is_terminal(self) -> bool:
        """Check if pipeline is in a terminal state."""
        return self.state in {"completed", "failed", "cancelled"}


class DataQualityChecker:
    """Check data quality metrics for pipeline inputs."""

    def __init__(self):
        self._rules: Dict[str, Dict[str, Any]] = {}
        self._violations: List[Dict[str, Any]] = []

    def add_rule(self, name: str, column: str, check_type: str,
                 threshold: Optional[float] = None):
        """Add a data quality rule."""
        self._rules[name] = {
            "column": column,
            "check_type": check_type,
            "threshold": threshold,
        }

    def check(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run all quality checks on a dataset. Short-circuits on first failure."""
        results = {}
        for rule_name, rule in sorted(self._rules.items()):
            col = rule["column"]
            values = [row.get(col) for row in data]
            total = len(values)
            if total == 0:
                results[rule_name] = {"passed": True, "metric": 1.0}
                continue

            if rule["check_type"] == "not_null":
                null_count = sum(1 for v in values if v is None)
                null_rate = null_count / total
                passed = null_rate <= (rule["threshold"] or 0.0)
                results[rule_name] = {"passed": passed, "metric": 1.0 - null_rate}

            elif rule["check_type"] == "unique":
                non_null = [v for v in values if v is not None]
                unique_rate = len(set(non_null)) / max(len(non_null), 1)
                passed = unique_rate >= (rule["threshold"] or 1.0)
                results[rule_name] = {"passed": passed, "metric": unique_rate}

            elif rule["check_type"] == "in_range":
                numeric = [v for v in values if isinstance(v, (int, float))]
                if not numeric:
                    results[rule_name] = {"passed": True, "metric": 1.0}
                    continue
                in_range = sum(1 for v in numeric
                              if rule.get("min", float("-inf")) <= v < rule.get("max", float("inf")))
                rate = in_range / len(numeric)
                passed = rate >= (rule["threshold"] or 1.0)
                results[rule_name] = {"passed": passed, "metric": rate}

            elif rule["check_type"] == "range":
                numeric = [v for v in values if isinstance(v, (int, float))]
                if not numeric:
                    results[rule_name] = {"passed": True, "metric": 1.0}
                    continue
                in_range = sum(1 for v in numeric
                              if rule.get("min", float("-inf")) <= v < rule.get("max", float("inf")))
                rate = in_range / len(numeric)
                passed = rate >= (rule["threshold"] or 1.0)
                results[rule_name] = {"passed": passed, "metric": rate}

            elif rule["check_type"] == "freshness":
                timestamps = [v for v in values if isinstance(v, (int, float))]
                if not timestamps:
                    results[rule_name] = {"passed": False, "metric": 0.0}
                    continue
                latest = max(timestamps)
                age = time.time() - latest
                max_age = rule["threshold"] or 3600
                passed = age < max_age
                results[rule_name] = {"passed": passed, "metric": max(0, 1.0 - age / max_age)}

            if not results.get(rule_name, {}).get("passed", True):
                self._violations.append({
                    "rule": rule_name,
                    "timestamp": time.time(),
                    "metric": results[rule_name]["metric"],
                })
                break  # Short-circuit on first failure

        return results

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self._violations)


app = {
    "service": "pipeline",
    "port": 8007,
}
