# LatticeForge - Greenfield Implementation Tasks

These tasks require implementing **new modules from scratch** that integrate with the existing LatticeForge service mesh platform. Each task must follow the established architectural patterns found in `services/` and `latticeforge/`.

---

## Task 1: Service Discovery Registry

### Overview

Implement a **Service Discovery Registry** that tracks service instances across the mesh, enabling dynamic endpoint resolution, health-aware routing, and graceful instance deregistration.

### Module Location

Create the following files:
- `services/discovery/__init__.py`
- `services/discovery/service.py`
- `latticeforge/discovery.py`

### Interface Contract

```python
# latticeforge/discovery.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Mapping, Optional, Sequence, Set

@dataclass(frozen=True)
class ServiceInstance:
    """Represents a single instance of a service in the mesh."""
    instance_id: str
    service_name: str
    endpoint: str          # e.g., "10.0.1.5:8080"
    region: str
    zone: str
    weight: int            # Load balancing weight (1-100)
    metadata: Dict[str, str]
    registered_at: datetime
    last_heartbeat: datetime

@dataclass(frozen=True)
class HealthStatus:
    """Health check result for a service instance."""
    instance_id: str
    healthy: bool
    latency_ms: int
    consecutive_failures: int
    last_check: datetime
    reason: Optional[str] = None


class ServiceRegistry:
    """
    Central registry for service discovery.

    Maintains a catalog of service instances with their health status,
    supports weighted load balancing, and handles graceful deregistration.
    """

    def __init__(self, heartbeat_timeout_s: int = 30, max_instances_per_service: int = 100) -> None:
        """
        Initialize the registry.

        Args:
            heartbeat_timeout_s: Seconds before an instance is marked stale
            max_instances_per_service: Maximum instances allowed per service name
        """
        ...

    def register(self, instance: ServiceInstance) -> bool:
        """
        Register a new service instance.

        Args:
            instance: The service instance to register

        Returns:
            True if registration succeeded, False if duplicate or limit exceeded

        Raises:
            ValueError: If instance has invalid fields
        """
        ...

    def deregister(self, instance_id: str) -> bool:
        """
        Remove an instance from the registry.

        Args:
            instance_id: The unique identifier of the instance

        Returns:
            True if instance was removed, False if not found
        """
        ...

    def heartbeat(self, instance_id: str) -> bool:
        """
        Update the last heartbeat timestamp for an instance.

        Args:
            instance_id: The unique identifier of the instance

        Returns:
            True if heartbeat recorded, False if instance not found
        """
        ...

    def update_health(self, status: HealthStatus) -> None:
        """
        Record a health check result for an instance.

        Args:
            status: The health status to record
        """
        ...

    def resolve(
        self,
        service_name: str,
        region: Optional[str] = None,
        healthy_only: bool = True,
        min_weight: int = 0,
    ) -> List[ServiceInstance]:
        """
        Resolve service name to list of instances.

        Args:
            service_name: Name of the service to resolve
            region: Optional region filter
            healthy_only: If True, exclude unhealthy instances
            min_weight: Minimum weight threshold for inclusion

        Returns:
            List of matching instances, sorted by weight descending
        """
        ...

    def select_instance(
        self,
        service_name: str,
        region: Optional[str] = None,
        strategy: str = "weighted-random",
    ) -> Optional[ServiceInstance]:
        """
        Select a single instance using the specified strategy.

        Args:
            service_name: Name of the service
            region: Optional region preference
            strategy: One of "weighted-random", "round-robin", "least-connections"

        Returns:
            Selected instance or None if no healthy instances available
        """
        ...

    def stale_instances(self) -> List[ServiceInstance]:
        """
        Return instances that haven't sent a heartbeat within timeout.

        Returns:
            List of stale instances
        """
        ...

    def service_topology(self) -> Dict[str, Dict[str, int]]:
        """
        Return topology map of services by region.

        Returns:
            Nested dict: {service_name: {region: instance_count}}
        """
        ...
```

```python
# services/discovery/service.py
from __future__ import annotations

from typing import Mapping, Optional, Sequence

from latticeforge.discovery import HealthStatus, ServiceInstance, ServiceRegistry

SERVICE_NAME = "discovery"
SERVICE_ROLE = "service registration and resolution"


def create_registry(config: Mapping[str, int]) -> ServiceRegistry:
    """
    Factory function to create a configured ServiceRegistry.

    Args:
        config: Configuration with keys "heartbeat_timeout_s", "max_instances"

    Returns:
        Configured ServiceRegistry instance
    """
    ...


def bulk_register(
    registry: ServiceRegistry,
    instances: Sequence[ServiceInstance],
    fail_fast: bool = False,
) -> dict[str, bool]:
    """
    Register multiple instances in batch.

    Args:
        registry: The registry to register instances in
        instances: Sequence of instances to register
        fail_fast: If True, stop on first failure

    Returns:
        Dict mapping instance_id to registration success
    """
    ...


def health_check_sweep(
    registry: ServiceRegistry,
    health_results: Sequence[HealthStatus],
    evict_threshold: int = 3,
) -> list[str]:
    """
    Process health check results and evict unhealthy instances.

    Args:
        registry: The registry to update
        health_results: Health check results to process
        evict_threshold: Consecutive failures before eviction

    Returns:
        List of evicted instance IDs
    """
    ...


def failover_candidates(
    registry: ServiceRegistry,
    service_name: str,
    exclude_regions: Sequence[str],
) -> list[ServiceInstance]:
    """
    Find failover candidates in non-excluded regions.

    Args:
        registry: The registry to query
        service_name: Service to find failover candidates for
        exclude_regions: Regions to exclude (e.g., degraded regions)

    Returns:
        List of healthy instances in non-excluded regions
    """
    ...
```

### Required Models

Add to `latticeforge/models.py`:
- `ServiceInstance` dataclass (as shown above)
- `HealthStatus` dataclass (as shown above)

### Architectural Patterns to Follow

1. **Service module structure**: Mirror `services/gateway/service.py` with `SERVICE_NAME` and `SERVICE_ROLE` constants
2. **Dataclass design**: Use `@dataclass(frozen=True)` for immutable value objects
3. **Error handling**: Raise `ValueError` for invalid inputs, return `False`/`None` for not-found cases
4. **Type hints**: Full type annotations following existing code style
5. **Sorting**: Use deterministic sorting (include secondary sort keys) like in `services/identity/service.py`

### Acceptance Criteria

1. **Unit tests** (`tests/unit/discovery_test.py`):
   - Test registration, deregistration, and duplicate handling
   - Test heartbeat timeout detection
   - Test health status updates and eviction
   - Test each selection strategy
   - Minimum 50 test cases

2. **Integration tests** (`tests/integration/discovery_flow_test.py`):
   - Test interaction with `services/gateway` for endpoint resolution
   - Test interaction with `services/resilience` for failover
   - Minimum 20 test cases

3. **Coverage**: Minimum 90% line coverage for new modules

4. **Contract compliance**: Add to `shared/contracts/contracts.py`:
   ```python
   SERVICE_SLO["discovery"] = {"latency_ms": 15, "availability": 0.9999}
   ```

---

## Task 2: Traffic Mirroring Service

### Overview

Implement a **Traffic Mirroring Service** that duplicates production traffic to shadow environments for testing, validation, and debugging without impacting production responses.

### Module Location

Create the following files:
- `services/mirror/__init__.py`
- `services/mirror/service.py`
- `latticeforge/mirror.py`

### Interface Contract

```python
# latticeforge/mirror.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

class MirrorMode(Enum):
    """Traffic mirroring modes."""
    FULL = "full"           # Mirror all traffic
    SAMPLED = "sampled"     # Sample by percentage
    FILTERED = "filtered"   # Mirror only matching traffic
    REPLAY = "replay"       # Replay captured traffic


@dataclass(frozen=True)
class MirrorConfig:
    """Configuration for a traffic mirror."""
    mirror_id: str
    source_service: str
    shadow_endpoint: str
    mode: MirrorMode
    sample_rate: float          # 0.0 to 1.0 for SAMPLED mode
    include_intents: tuple[str, ...]   # Filter for FILTERED mode
    exclude_intents: tuple[str, ...]   # Exclusions for FILTERED mode
    timeout_ms: int
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class MirroredRequest:
    """A request that has been mirrored."""
    request_id: str
    trace_id: str
    source_service: str
    intent: str
    payload: Dict[str, Any]
    headers: Dict[str, str]
    mirrored_at: datetime


@dataclass(frozen=True)
class MirrorResult:
    """Result of processing a mirrored request."""
    request_id: str
    shadow_endpoint: str
    success: bool
    latency_ms: int
    response_code: Optional[int]
    diff_detected: bool
    diff_summary: Optional[str]


class TrafficMirror:
    """
    Manages traffic mirroring to shadow environments.

    Supports multiple mirroring strategies including full duplication,
    sampling, and intent-based filtering.
    """

    def __init__(self, max_mirrors: int = 10, buffer_size: int = 1000) -> None:
        """
        Initialize the traffic mirror.

        Args:
            max_mirrors: Maximum concurrent mirror configurations
            buffer_size: Size of the async send buffer per mirror
        """
        ...

    def add_mirror(self, config: MirrorConfig) -> bool:
        """
        Add a new mirror configuration.

        Args:
            config: Mirror configuration to add

        Returns:
            True if added, False if duplicate or limit exceeded

        Raises:
            ValueError: If config has invalid fields
        """
        ...

    def remove_mirror(self, mirror_id: str) -> bool:
        """
        Remove a mirror configuration.

        Args:
            mirror_id: ID of mirror to remove

        Returns:
            True if removed, False if not found
        """
        ...

    def enable_mirror(self, mirror_id: str) -> bool:
        """Enable a disabled mirror."""
        ...

    def disable_mirror(self, mirror_id: str) -> bool:
        """Disable a mirror without removing it."""
        ...

    def should_mirror(self, config: MirrorConfig, intent: str, sample_seed: float) -> bool:
        """
        Determine if a request should be mirrored based on config.

        Args:
            config: Mirror configuration
            intent: Request intent
            sample_seed: Random value [0,1) for sampling decisions

        Returns:
            True if request should be mirrored
        """
        ...

    def capture(
        self,
        request_id: str,
        trace_id: str,
        source_service: str,
        intent: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> List[MirroredRequest]:
        """
        Capture a request for mirroring to applicable shadows.

        Args:
            request_id: Unique request identifier
            trace_id: Distributed trace ID
            source_service: Originating service name
            intent: Request intent/type
            payload: Request payload
            headers: Request headers

        Returns:
            List of MirroredRequest objects queued for delivery
        """
        ...

    def pending_count(self, mirror_id: Optional[str] = None) -> int:
        """
        Get count of pending mirrored requests.

        Args:
            mirror_id: Optional filter by mirror ID

        Returns:
            Count of pending requests
        """
        ...

    def drain(self, mirror_id: str, limit: int = 100) -> List[MirroredRequest]:
        """
        Drain pending requests from a mirror's buffer.

        Args:
            mirror_id: Mirror to drain from
            limit: Maximum requests to return

        Returns:
            List of pending MirroredRequest objects
        """
        ...

    def stats(self) -> Dict[str, Dict[str, int]]:
        """
        Get statistics for all mirrors.

        Returns:
            Dict: {mirror_id: {captured: N, dropped: N, pending: N}}
        """
        ...


def compare_responses(
    production: Dict[str, Any],
    shadow: Dict[str, Any],
    ignore_fields: Sequence[str] = (),
) -> tuple[bool, Optional[str]]:
    """
    Compare production and shadow responses for differences.

    Args:
        production: Production response payload
        shadow: Shadow response payload
        ignore_fields: Fields to exclude from comparison

    Returns:
        Tuple of (has_diff, diff_summary)
    """
    ...
```

```python
# services/mirror/service.py
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from latticeforge.mirror import (
    MirrorConfig,
    MirrorMode,
    MirroredRequest,
    MirrorResult,
    TrafficMirror,
    compare_responses,
)

SERVICE_NAME = "mirror"
SERVICE_ROLE = "shadow traffic mirroring"


def create_mirror_from_spec(spec: Mapping[str, Any]) -> MirrorConfig:
    """
    Create a MirrorConfig from a specification dict.

    Args:
        spec: Dict with mirror configuration fields

    Returns:
        Configured MirrorConfig instance

    Raises:
        ValueError: If spec is missing required fields or has invalid values
    """
    ...


def dispatch_to_shadow(
    request: MirroredRequest,
    shadow_endpoint: str,
    timeout_ms: int,
    shadow_handler: Any,  # Callable that sends to shadow
) -> MirrorResult:
    """
    Dispatch a mirrored request to shadow environment.

    Args:
        request: The mirrored request to send
        shadow_endpoint: Target shadow endpoint
        timeout_ms: Request timeout
        shadow_handler: Handler to invoke shadow service

    Returns:
        MirrorResult with outcome
    """
    ...


def batch_dispatch(
    mirror: TrafficMirror,
    mirror_id: str,
    shadow_handler: Any,
    batch_size: int = 50,
) -> list[MirrorResult]:
    """
    Dispatch a batch of pending mirrored requests.

    Args:
        mirror: TrafficMirror instance
        mirror_id: Mirror to dispatch from
        shadow_handler: Handler to invoke shadow service
        batch_size: Maximum requests per batch

    Returns:
        List of MirrorResult objects
    """
    ...


def analyze_diffs(
    results: Sequence[MirrorResult],
    threshold: float = 0.05,
) -> dict[str, Any]:
    """
    Analyze diff patterns across mirror results.

    Args:
        results: Sequence of MirrorResult objects
        threshold: Alert threshold for diff rate

    Returns:
        Analysis report with diff patterns and recommendations
    """
    ...
```

### Required Models

Add to `latticeforge/models.py`:
- `MirrorMode` enum
- `MirrorConfig` dataclass
- `MirroredRequest` dataclass
- `MirrorResult` dataclass

### Architectural Patterns to Follow

1. **Buffer management**: Follow patterns from `latticeforge/queue.py` for request buffering
2. **Statistics tracking**: Mirror the stats pattern from `AuditLedger` in `services/audit/service.py`
3. **Configuration validation**: Follow `derive_context` pattern from `services/identity/service.py`
4. **Comparison logic**: Use deterministic comparison with sorted keys for reproducibility

### Acceptance Criteria

1. **Unit tests** (`tests/unit/mirror_test.py`):
   - Test all mirror modes (FULL, SAMPLED, FILTERED, REPLAY)
   - Test buffer overflow handling
   - Test enable/disable lifecycle
   - Test comparison logic with edge cases
   - Minimum 60 test cases

2. **Integration tests** (`tests/integration/mirror_flow_test.py`):
   - Test integration with `services/gateway` for request capture
   - Test integration with `services/audit` for mirror event logging
   - Minimum 25 test cases

3. **Coverage**: Minimum 90% line coverage

4. **Contract compliance**: Add to `shared/contracts/contracts.py`:
   ```python
   SERVICE_SLO["mirror"] = {"latency_ms": 5, "availability": 0.999}
   ```

---

## Task 3: Distributed Tracing Collector

### Overview

Implement a **Distributed Tracing Collector** that aggregates spans from across the service mesh, builds trace trees, computes latency breakdowns, and identifies anomalous traces.

### Module Location

Create the following files:
- `services/tracing/__init__.py`
- `services/tracing/service.py`
- `latticeforge/tracing.py`

### Interface Contract

```python
# latticeforge/tracing.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

class SpanKind(Enum):
    """Type of span in a trace."""
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"


class SpanStatus(Enum):
    """Status of a span."""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Span:
    """A single span in a distributed trace."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation_name: str
    kind: SpanKind
    status: SpanStatus
    start_time: datetime
    end_time: datetime
    tags: Dict[str, str]
    logs: tuple[Dict[str, Any], ...]

    @property
    def duration_ms(self) -> int:
        """Calculate span duration in milliseconds."""
        ...


@dataclass(frozen=True)
class TraceTree:
    """A complete trace assembled from spans."""
    trace_id: str
    root_span: Span
    spans: tuple[Span, ...]
    total_duration_ms: int
    service_count: int
    error_count: int
    assembled_at: datetime


@dataclass
class LatencyBreakdown:
    """Latency contribution by service."""
    service_name: str
    total_ms: int
    self_ms: int          # Time in this service excluding children
    span_count: int
    error_rate: float


class TraceCollector:
    """
    Collects and aggregates distributed traces from the service mesh.

    Assembles spans into complete traces, computes latency breakdowns,
    and identifies anomalous patterns.
    """

    def __init__(
        self,
        max_spans_per_trace: int = 500,
        trace_ttl_seconds: int = 3600,
        anomaly_threshold_ms: int = 1000,
    ) -> None:
        """
        Initialize the trace collector.

        Args:
            max_spans_per_trace: Maximum spans to retain per trace
            trace_ttl_seconds: Time-to-live for incomplete traces
            anomaly_threshold_ms: Latency threshold for anomaly detection
        """
        ...

    def ingest(self, span: Span) -> bool:
        """
        Ingest a span into the collector.

        Args:
            span: Span to ingest

        Returns:
            True if ingested, False if trace is full or expired
        """
        ...

    def ingest_batch(self, spans: Sequence[Span]) -> dict[str, int]:
        """
        Ingest multiple spans.

        Args:
            spans: Spans to ingest

        Returns:
            Dict with counts: {ingested: N, dropped: N, duplicates: N}
        """
        ...

    def assemble(self, trace_id: str) -> Optional[TraceTree]:
        """
        Assemble a complete trace from collected spans.

        Args:
            trace_id: ID of trace to assemble

        Returns:
            Assembled TraceTree or None if insufficient spans
        """
        ...

    def get_span(self, trace_id: str, span_id: str) -> Optional[Span]:
        """
        Retrieve a specific span.

        Args:
            trace_id: Trace containing the span
            span_id: ID of span to retrieve

        Returns:
            Span or None if not found
        """
        ...

    def children(self, trace_id: str, parent_span_id: str) -> List[Span]:
        """
        Get child spans of a given parent.

        Args:
            trace_id: Trace ID
            parent_span_id: Parent span ID

        Returns:
            List of child spans sorted by start_time
        """
        ...

    def latency_breakdown(self, trace_id: str) -> List[LatencyBreakdown]:
        """
        Compute latency breakdown by service for a trace.

        Args:
            trace_id: Trace to analyze

        Returns:
            List of LatencyBreakdown sorted by total_ms descending
        """
        ...

    def critical_path(self, trace_id: str) -> List[Span]:
        """
        Identify the critical path (longest sequential chain) in a trace.

        Args:
            trace_id: Trace to analyze

        Returns:
            List of spans on the critical path in execution order
        """
        ...

    def anomalous_traces(self, limit: int = 100) -> List[TraceTree]:
        """
        Return traces exceeding the anomaly threshold.

        Args:
            limit: Maximum traces to return

        Returns:
            List of anomalous traces sorted by duration descending
        """
        ...

    def service_latency_percentiles(
        self,
        service_name: str,
        percentiles: Sequence[int] = (50, 90, 95, 99),
    ) -> Dict[int, int]:
        """
        Compute latency percentiles for a service across all traces.

        Args:
            service_name: Service to analyze
            percentiles: Percentile values to compute

        Returns:
            Dict mapping percentile to latency_ms
        """
        ...

    def incomplete_traces(self) -> List[str]:
        """
        Return trace IDs that have spans but no root span.

        Returns:
            List of incomplete trace IDs
        """
        ...

    def prune_expired(self) -> int:
        """
        Remove traces older than TTL.

        Returns:
            Count of pruned traces
        """
        ...


def span_from_dict(data: Mapping[str, Any]) -> Span:
    """
    Create a Span from a dictionary payload.

    Args:
        data: Dict with span fields

    Returns:
        Constructed Span

    Raises:
        ValueError: If required fields are missing
    """
    ...


def trace_to_flamegraph(trace: TraceTree) -> Dict[str, Any]:
    """
    Convert a trace tree to flamegraph-compatible format.

    Args:
        trace: TraceTree to convert

    Returns:
        Dict in flamegraph JSON format
    """
    ...
```

```python
# services/tracing/service.py
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from latticeforge.tracing import (
    LatencyBreakdown,
    Span,
    SpanKind,
    SpanStatus,
    TraceCollector,
    TraceTree,
    span_from_dict,
    trace_to_flamegraph,
)

SERVICE_NAME = "tracing"
SERVICE_ROLE = "distributed trace collection"


def create_collector(config: Mapping[str, int]) -> TraceCollector:
    """
    Factory function to create a configured TraceCollector.

    Args:
        config: Configuration with collector settings

    Returns:
        Configured TraceCollector instance
    """
    ...


def inject_trace_context(
    headers: Dict[str, str],
    trace_id: str,
    span_id: str,
    sampled: bool = True,
) -> Dict[str, str]:
    """
    Inject trace context into request headers (W3C Trace Context format).

    Args:
        headers: Existing headers dict
        trace_id: Trace ID to inject
        span_id: Span ID to inject
        sampled: Whether this trace is sampled

    Returns:
        Headers dict with trace context added
    """
    ...


def extract_trace_context(headers: Mapping[str, str]) -> Optional[Dict[str, str]]:
    """
    Extract trace context from request headers.

    Args:
        headers: Request headers

    Returns:
        Dict with trace_id, parent_span_id, sampled or None
    """
    ...


def slo_compliance_report(
    collector: TraceCollector,
    slo_by_service: Mapping[str, int],
) -> Dict[str, Dict[str, Any]]:
    """
    Generate SLO compliance report from collected traces.

    Args:
        collector: TraceCollector with trace data
        slo_by_service: Max latency SLO by service name

    Returns:
        Report: {service: {slo_ms, p99_ms, compliance_pct, violations}}
    """
    ...


def dependency_graph(collector: TraceCollector) -> Dict[str, Set[str]]:
    """
    Build service dependency graph from traces.

    Args:
        collector: TraceCollector with trace data

    Returns:
        Dict: {service: {downstream_services}}
    """
    ...


def slow_span_analysis(
    collector: TraceCollector,
    threshold_ms: int,
    limit: int = 50,
) -> list[Dict[str, Any]]:
    """
    Find and analyze spans exceeding latency threshold.

    Args:
        collector: TraceCollector with trace data
        threshold_ms: Latency threshold
        limit: Maximum spans to return

    Returns:
        List of slow span analysis records
    """
    ...
```

### Required Models

Add to `latticeforge/models.py`:
- `SpanKind` enum
- `SpanStatus` enum
- `Span` dataclass
- `TraceTree` dataclass
- `LatencyBreakdown` dataclass

### Architectural Patterns to Follow

1. **Tree assembly**: Use patterns from `latticeforge/dependency.py` for building span trees
2. **Percentile computation**: Follow `latticeforge/statistics.py` for percentile calculations
3. **TTL management**: Mirror the stale detection pattern from `ServiceRegistry`
4. **Data export**: Follow `export_trace` pattern from `services/audit/service.py`

### Acceptance Criteria

1. **Unit tests** (`tests/unit/tracing_test.py`):
   - Test span ingestion and deduplication
   - Test trace assembly with complex parent-child relationships
   - Test critical path detection
   - Test percentile computation accuracy
   - Test TTL expiration and pruning
   - Minimum 80 test cases

2. **Integration tests** (`tests/integration/tracing_flow_test.py`):
   - Test with `services/gateway` for context propagation
   - Test with `services/analytics` for SLO compliance
   - Test with `services/audit` for trace export
   - Minimum 30 test cases

3. **Coverage**: Minimum 90% line coverage

4. **Contract compliance**: Add to `shared/contracts/contracts.py`:
   ```python
   SERVICE_SLO["tracing"] = {"latency_ms": 25, "availability": 0.999}

   REQUIRED_SPAN_FIELDS = {
       "span_id",
       "trace_id",
       "service_name",
       "operation_name",
       "start_time",
       "end_time",
       "status",
   }
   ```

---

## General Requirements

### Code Style

- Follow existing patterns in `latticeforge/` and `services/`
- Use `from __future__ import annotations` in all new files
- Full type hints on all public functions and methods
- Docstrings for all public classes, methods, and functions
- Use `@dataclass(frozen=True)` for immutable value objects

### Testing Standards

- Tests go in `tests/unit/` and `tests/integration/`
- Test file naming: `<module>_test.py`
- Use `unittest` framework consistent with existing tests
- Include edge cases: empty inputs, boundary values, error conditions

### Integration Points

Each new service should integrate with existing services:

| New Service | Integrates With |
|-------------|-----------------|
| `discovery` | `gateway` (endpoint resolution), `resilience` (failover) |
| `mirror` | `gateway` (capture), `audit` (logging), `analytics` (diff analysis) |
| `tracing` | `gateway` (context propagation), `analytics` (SLO), `audit` (export) |

### Deliverables Checklist

For each task, deliver:
- [ ] Core module in `latticeforge/`
- [ ] Service module in `services/<name>/`
- [ ] `__init__.py` files for new packages
- [ ] Unit tests with 50+ test cases
- [ ] Integration tests with 20+ test cases
- [ ] Updates to `shared/contracts/contracts.py`
- [ ] 90%+ code coverage
