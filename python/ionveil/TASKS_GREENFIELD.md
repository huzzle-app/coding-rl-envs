# IonVeil Greenfield Tasks

This document defines greenfield implementation tasks for the IonVeil policy enforcement and dispatch system. Each task requires implementing a new module from scratch while following the existing architectural patterns found in the codebase.

---

## Task 1: Policy Simulator Service

### Overview

Implement a Policy Simulator that allows operators to test policy changes in a sandboxed environment before deploying them to production. The simulator must accurately model the effects of escalation thresholds, de-escalation rules, and failure bursts on system behavior without affecting live operations.

### Module Location

Create: `services/simulator/__init__.py` and `services/simulator/engine.py`

### Interface Contract

```python
"""
IonVeil Policy Simulator Service
================================
Simulates policy changes in a sandboxed environment to predict system
behavior under various failure scenarios before production deployment.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional


class SimulationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PolicyScenario:
    """Defines a policy configuration to simulate."""
    name: str
    policy_order: list[str]  # e.g., ["normal", "watch", "restricted", "halted"]
    escalation_threshold: int  # failure_burst count to trigger escalation
    deescalation_thresholds: dict[str, int]  # policy -> success_streak required
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailurePattern:
    """Defines a pattern of failures/successes to inject."""
    pattern_id: str
    events: list[tuple[int, bool]]  # (timestamp_offset_seconds, is_success)
    description: str = ""


@dataclass
class SimulationResult:
    """Results of a policy simulation run."""
    simulation_id: str
    scenario: PolicyScenario
    failure_pattern: FailurePattern
    policy_transitions: list[dict[str, Any]]  # [{from, to, timestamp, reason}]
    final_policy: str
    total_escalations: int
    total_deescalations: int
    time_in_each_policy: dict[str, float]  # policy -> seconds
    sla_compliance_rate: float  # 0.0 - 1.0
    status: SimulationStatus
    error_message: Optional[str] = None


class PolicySimulator:
    """
    Simulates policy behavior under various failure scenarios.

    Thread-safe implementation that can run multiple simulations
    concurrently without affecting production policy state.
    """

    def __init__(self, max_concurrent: int = 10) -> None:
        """
        Initialize the policy simulator.

        Args:
            max_concurrent: Maximum number of concurrent simulations.
        """
        ...

    def create_simulation(
        self,
        scenario: PolicyScenario,
        failure_pattern: FailurePattern,
        duration_seconds: int = 3600,
    ) -> str:
        """
        Create a new simulation run.

        Args:
            scenario: The policy configuration to test.
            failure_pattern: The failure/success pattern to inject.
            duration_seconds: How long to simulate (virtual time).

        Returns:
            Unique simulation ID.
        """
        ...

    def run_simulation(self, simulation_id: str) -> SimulationResult:
        """
        Execute a simulation and return results.

        Args:
            simulation_id: ID from create_simulation().

        Returns:
            Complete simulation results.

        Raises:
            KeyError: If simulation_id not found.
            RuntimeError: If simulation already running.
        """
        ...

    def get_simulation_status(self, simulation_id: str) -> SimulationStatus:
        """
        Get the current status of a simulation.

        Args:
            simulation_id: ID from create_simulation().

        Returns:
            Current simulation status.
        """
        ...

    def cancel_simulation(self, simulation_id: str) -> bool:
        """
        Cancel a running or pending simulation.

        Args:
            simulation_id: ID from create_simulation().

        Returns:
            True if cancelled, False if already completed.
        """
        ...

    def compare_scenarios(
        self,
        scenarios: list[PolicyScenario],
        failure_pattern: FailurePattern,
    ) -> dict[str, SimulationResult]:
        """
        Run the same failure pattern against multiple scenarios for comparison.

        Args:
            scenarios: List of policy configurations to compare.
            failure_pattern: The failure pattern to test each against.

        Returns:
            Dict mapping scenario name to simulation result.
        """
        ...

    def generate_recommendation(
        self,
        results: list[SimulationResult],
    ) -> dict[str, Any]:
        """
        Analyze simulation results and generate policy recommendations.

        Args:
            results: List of simulation results to analyze.

        Returns:
            Recommendation dict with suggested thresholds and reasoning.
        """
        ...


class ScenarioBuilder:
    """Fluent builder for creating PolicyScenario instances."""

    def __init__(self, name: str) -> None:
        """Start building a scenario with the given name."""
        ...

    def with_policy_order(self, order: list[str]) -> "ScenarioBuilder":
        """Set the policy progression order."""
        ...

    def with_escalation_threshold(self, threshold: int) -> "ScenarioBuilder":
        """Set the failure burst count that triggers escalation."""
        ...

    def with_deescalation_threshold(
        self, policy: str, success_streak: int
    ) -> "ScenarioBuilder":
        """Set the success streak required to de-escalate from a policy."""
        ...

    def build(self) -> PolicyScenario:
        """Build and return the PolicyScenario."""
        ...


class FailurePatternGenerator:
    """Generate common failure patterns for testing."""

    @staticmethod
    def constant_failure_rate(
        rate: float,
        duration_seconds: int,
        events_per_second: float = 1.0,
    ) -> FailurePattern:
        """
        Generate a pattern with constant failure rate.

        Args:
            rate: Failure rate (0.0 - 1.0).
            duration_seconds: Total duration of the pattern.
            events_per_second: How many events occur per second.

        Returns:
            FailurePattern with uniformly distributed failures.
        """
        ...

    @staticmethod
    def burst_failure(
        burst_size: int,
        burst_interval_seconds: int,
        duration_seconds: int,
    ) -> FailurePattern:
        """
        Generate a pattern with periodic failure bursts.

        Args:
            burst_size: Number of consecutive failures per burst.
            burst_interval_seconds: Time between burst starts.
            duration_seconds: Total duration of the pattern.

        Returns:
            FailurePattern with periodic bursts.
        """
        ...

    @staticmethod
    def cascading_failure(
        initial_rate: float,
        escalation_factor: float,
        recovery_after_seconds: int,
        duration_seconds: int,
    ) -> FailurePattern:
        """
        Generate a pattern simulating cascading failures with eventual recovery.

        Args:
            initial_rate: Starting failure rate.
            escalation_factor: How much failure rate increases per interval.
            recovery_after_seconds: When recovery begins.
            duration_seconds: Total duration of the pattern.

        Returns:
            FailurePattern simulating cascade and recovery.
        """
        ...
```

### Required Models/Data Structures

- `PolicyScenario`: Encapsulates a complete policy configuration
- `FailurePattern`: Defines a sequence of success/failure events
- `SimulationResult`: Contains all outputs from a simulation run
- `SimulationStatus`: Enum for tracking simulation lifecycle

### Architectural Requirements

1. **Thread Safety**: Use `threading.Lock` for all shared state, following the pattern in `ionveil/policy.py` (`PolicyEngine`)
2. **Dataclasses**: Use `@dataclass` for all data structures, matching `ionveil/models.py` style
3. **Validation**: Implement input validation similar to `validate_dispatch_order()` in `ionveil/models.py`
4. **Integration**: Must work with the existing `PolicyEngine` from `ionveil/policy.py` without modifying it
5. **Stateless Functions**: Include pure utility functions alongside the class, following the module pattern in `ionveil/dispatch.py`

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/simulator_test.py`):
   - Test scenario creation and validation
   - Test all failure pattern generators
   - Test simulation execution with known inputs
   - Test concurrent simulation handling
   - Test cancellation behavior

2. **Integration Tests** (create `tests/integration/simulator_flow_test.py`):
   - Test comparison of multiple scenarios
   - Test recommendation generation
   - Test integration with PolicyEngine state transitions

3. **Coverage Requirements**:
   - Minimum 85% line coverage
   - All public methods must have at least one test

4. **Contract Validation**:
   - Add service definition to `shared/contracts/contracts.py`:
     ```python
     "simulator": {
         "id": "simulator",
         "port": 8110,
         "health": "/health",
         "description": "Policy simulation and testing service",
         "deps": ["policy"],
     }
     ```

---

## Task 2: Dispatch Analytics Dashboard Backend

### Overview

Implement a real-time analytics backend that aggregates dispatch metrics, computes KPIs, and provides data for operational dashboards. The service must support time-windowed aggregations, geographic breakdowns, and trend analysis while handling high-throughput event streams.

### Module Location

Create: `services/dashboard/__init__.py` and `services/dashboard/aggregator.py`

### Interface Contract

```python
"""
IonVeil Dispatch Analytics Dashboard Backend
=============================================
Real-time analytics aggregation for operational dashboards showing
dispatch performance, resource utilization, and SLA compliance trends.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional


class TimeWindow(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_6 = "6h"
    DAY_1 = "1d"


class AggregationType(str, Enum):
    SUM = "sum"
    COUNT = "count"
    AVERAGE = "avg"
    PERCENTILE_50 = "p50"
    PERCENTILE_90 = "p90"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"
    MIN = "min"
    MAX = "max"


@dataclass
class DispatchEvent:
    """A single dispatch event for analytics."""
    event_id: str
    org_id: str
    dispatch_id: str
    timestamp: datetime
    severity: int  # 1-5
    response_time_minutes: float
    distance_km: float
    region: str
    unit_type: str
    sla_met: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedMetric:
    """A single aggregated metric value."""
    metric_name: str
    value: float
    window_start: datetime
    window_end: datetime
    dimensions: dict[str, str]  # e.g., {"region": "north", "severity": "5"}
    sample_count: int


@dataclass
class DashboardSnapshot:
    """Complete dashboard state at a point in time."""
    org_id: str
    timestamp: datetime
    metrics: list[AggregatedMetric]
    active_dispatches: int
    pending_dispatches: int
    sla_compliance_rate: float
    average_response_time: float
    alerts: list[dict[str, Any]]


@dataclass
class TrendPoint:
    """A single point in a trend line."""
    timestamp: datetime
    value: float


@dataclass
class TrendAnalysis:
    """Trend analysis result with direction and forecast."""
    metric_name: str
    points: list[TrendPoint]
    trend_direction: str  # "increasing", "decreasing", "stable"
    slope: float
    forecast_next_hour: float
    confidence: float  # 0.0 - 1.0


class DispatchAggregator:
    """
    Aggregates dispatch events into dashboard-ready metrics.

    Maintains sliding window aggregations and supports real-time
    updates via event streaming.
    """

    def __init__(
        self,
        retention_hours: int = 24,
        flush_interval_seconds: float = 10.0,
    ) -> None:
        """
        Initialize the aggregator.

        Args:
            retention_hours: How long to retain aggregated data.
            flush_interval_seconds: How often to flush partial aggregates.
        """
        ...

    async def ingest_event(self, event: DispatchEvent) -> None:
        """
        Ingest a single dispatch event for aggregation.

        Args:
            event: The dispatch event to process.
        """
        ...

    async def ingest_batch(self, events: list[DispatchEvent]) -> int:
        """
        Ingest multiple events in a batch.

        Args:
            events: List of dispatch events.

        Returns:
            Number of events successfully ingested.
        """
        ...

    async def get_metric(
        self,
        org_id: str,
        metric_name: str,
        window: TimeWindow,
        aggregation: AggregationType,
        dimensions: Optional[dict[str, str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[AggregatedMetric]:
        """
        Query aggregated metrics.

        Args:
            org_id: Organisation to query.
            metric_name: Name of the metric (e.g., "response_time", "dispatch_count").
            window: Time window for aggregation.
            aggregation: Type of aggregation to apply.
            dimensions: Optional dimension filters.
            start: Query start time (default: 1 hour ago).
            end: Query end time (default: now).

        Returns:
            List of aggregated metric values.
        """
        ...

    async def get_dashboard_snapshot(
        self,
        org_id: str,
    ) -> DashboardSnapshot:
        """
        Get a complete dashboard snapshot for an organization.

        Args:
            org_id: Organisation to query.

        Returns:
            Complete dashboard state with all key metrics.
        """
        ...

    async def subscribe_to_updates(
        self,
        org_id: str,
        metrics: list[str],
    ) -> AsyncIterator[AggregatedMetric]:
        """
        Subscribe to real-time metric updates.

        Args:
            org_id: Organisation to subscribe to.
            metrics: List of metric names to receive updates for.

        Yields:
            AggregatedMetric updates as they occur.
        """
        ...

    def get_buffer_size(self) -> int:
        """Return the current size of the event buffer."""
        ...

    def flush(self) -> int:
        """
        Manually flush pending aggregations.

        Returns:
            Number of aggregations flushed.
        """
        ...


class TrendAnalyzer:
    """Analyzes metric trends and generates forecasts."""

    def __init__(self, aggregator: DispatchAggregator) -> None:
        """
        Initialize with an aggregator for data access.

        Args:
            aggregator: The aggregator to query for historical data.
        """
        ...

    async def analyze_trend(
        self,
        org_id: str,
        metric_name: str,
        window: TimeWindow,
        lookback_periods: int = 24,
    ) -> TrendAnalysis:
        """
        Analyze the trend of a metric over time.

        Args:
            org_id: Organisation to analyze.
            metric_name: Metric to analyze.
            window: Time window granularity.
            lookback_periods: Number of periods to analyze.

        Returns:
            TrendAnalysis with direction, slope, and forecast.
        """
        ...

    async def detect_anomalies(
        self,
        org_id: str,
        metric_name: str,
        window: TimeWindow,
        sensitivity: float = 2.0,
    ) -> list[dict[str, Any]]:
        """
        Detect anomalies in metric values.

        Args:
            org_id: Organisation to analyze.
            metric_name: Metric to check.
            window: Time window for analysis.
            sensitivity: Standard deviation multiplier for anomaly threshold.

        Returns:
            List of detected anomalies with timestamps and values.
        """
        ...


class GeographicBreakdown:
    """Compute geographic breakdowns of dispatch metrics."""

    def __init__(self, aggregator: DispatchAggregator) -> None:
        """
        Initialize with an aggregator for data access.

        Args:
            aggregator: The aggregator to query.
        """
        ...

    async def get_regional_summary(
        self,
        org_id: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, dict[str, float]]:
        """
        Get dispatch metrics broken down by region.

        Args:
            org_id: Organisation to query.
            start: Query start time.
            end: Query end time.

        Returns:
            Dict mapping region to metric dict.
            Example: {"north": {"dispatch_count": 45, "avg_response": 8.2}}
        """
        ...

    async def get_heatmap_data(
        self,
        org_id: str,
        metric_name: str,
        grid_size: tuple[int, int] = (10, 10),
    ) -> list[dict[str, Any]]:
        """
        Get heatmap-ready data for geographic visualization.

        Args:
            org_id: Organisation to query.
            metric_name: Metric to aggregate.
            grid_size: (rows, cols) for the heatmap grid.

        Returns:
            List of {row, col, value} dicts for heatmap rendering.
        """
        ...
```

### Required Models/Data Structures

- `DispatchEvent`: Input event for aggregation
- `AggregatedMetric`: Single aggregated value with dimensions
- `DashboardSnapshot`: Complete dashboard state
- `TrendPoint` / `TrendAnalysis`: Trend analysis outputs
- `TimeWindow` / `AggregationType`: Configuration enums

### Architectural Requirements

1. **Async Pattern**: Use `async/await` consistently, following `services/analytics/metrics.py`
2. **Streaming**: Implement `AsyncIterator` for real-time subscriptions like `MetricsCollector.stream_metrics()`
3. **Thread Safety**: Protect shared buffers with locks when accessed from sync contexts
4. **Statistics Integration**: Reuse `ionveil/statistics.py` functions (`percentile`, `mean`, `moving_average`)
5. **Heatmap Integration**: Follow the `generate_heatmap()` pattern from `ionveil/statistics.py`
6. **Dataclass Models**: Use frozen dataclasses for immutable event data

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/dashboard_test.py`):
   - Test event ingestion and aggregation
   - Test all aggregation types (sum, count, avg, percentiles)
   - Test time window calculations
   - Test dimension filtering

2. **Integration Tests** (create `tests/integration/dashboard_flow_test.py`):
   - Test real-time subscription flow
   - Test trend analysis accuracy
   - Test geographic breakdown with mock coordinates
   - Test high-throughput ingestion (1000+ events)

3. **Coverage Requirements**:
   - Minimum 85% line coverage
   - All async methods must have tests

4. **Contract Validation**:
   - Add service definition to `shared/contracts/contracts.py`:
     ```python
     "dashboard": {
         "id": "dashboard",
         "port": 8111,
         "health": "/health",
         "description": "Real-time dispatch analytics dashboard backend",
         "deps": ["analytics", "dispatch"],
     }
     ```

---

## Task 3: SLA Monitoring and Alerting Service

### Overview

Implement a proactive SLA monitoring service that tracks compliance in real-time, generates alerts when SLA breaches are imminent or occur, and provides escalation workflows. The service must integrate with the existing notification channels and maintain an audit trail of all alerts.

### Module Location

Create: `services/alerts/__init__.py` and `services/alerts/monitor.py`

### Interface Contract

```python
"""
IonVeil SLA Monitoring and Alerting Service
=============================================
Proactive SLA monitoring with configurable alert rules, escalation
chains, and integration with notification channels.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"


class EscalationLevel(int, Enum):
    L1_OPERATOR = 1
    L2_SUPERVISOR = 2
    L3_MANAGER = 3
    L4_EXECUTIVE = 4


@dataclass
class AlertRule:
    """Defines when and how to generate alerts."""
    rule_id: str
    name: str
    description: str
    condition_type: str  # "sla_breach", "sla_warning", "threshold", "pattern"
    threshold_config: dict[str, Any]
    # e.g., {"sla_remaining_pct": 25, "consecutive_breaches": 3}
    severity: AlertSeverity
    notification_channels: list[str]  # ["email", "sms", "slack", "pagerduty"]
    escalation_after_minutes: Optional[int] = None
    suppression_window_minutes: int = 5
    enabled: bool = True


@dataclass
class Alert:
    """A generated alert instance."""
    alert_id: str
    rule_id: str
    org_id: str
    incident_id: Optional[str]
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    escalation_level: EscalationLevel = EscalationLevel.L1_OPERATOR
    escalation_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationPolicy:
    """Defines escalation chain for alerts."""
    policy_id: str
    name: str
    levels: list[dict[str, Any]]
    # [{"level": 1, "timeout_minutes": 15, "channels": ["email", "slack"]}, ...]
    repeat_after_minutes: Optional[int] = None
    max_escalations: int = 3


@dataclass
class SLAViolation:
    """Details of an SLA violation."""
    incident_id: str
    org_id: str
    priority: int
    sla_target_minutes: int
    actual_minutes: float
    breach_time: datetime
    breach_magnitude: float  # how much over SLA (1.5 = 50% over)


class SLAMonitorService:
    """
    Monitors SLA compliance and generates alerts for violations.

    Integrates with the dispatch system to track active incidents
    and proactively alert when SLA breaches are imminent.
    """

    def __init__(
        self,
        check_interval_seconds: float = 30.0,
        notification_callback: Optional[Callable[[Alert], None]] = None,
    ) -> None:
        """
        Initialize the SLA monitor.

        Args:
            check_interval_seconds: How often to check for SLA violations.
            notification_callback: Function to call when alerts are generated.
        """
        ...

    async def start(self) -> None:
        """Start the background monitoring loop."""
        ...

    async def stop(self) -> None:
        """Stop the monitoring loop gracefully."""
        ...

    def add_rule(self, rule: AlertRule) -> None:
        """
        Add or update an alert rule.

        Args:
            rule: The alert rule to add.
        """
        ...

    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove an alert rule.

        Args:
            rule_id: ID of the rule to remove.

        Returns:
            True if removed, False if not found.
        """
        ...

    def get_rules(self, org_id: Optional[str] = None) -> list[AlertRule]:
        """
        Get all alert rules, optionally filtered by org.

        Args:
            org_id: Optional org filter.

        Returns:
            List of matching rules.
        """
        ...

    async def check_incident(
        self,
        incident_id: str,
        org_id: str,
        priority: int,
        dispatch_time: datetime,
        current_time: Optional[datetime] = None,
    ) -> list[Alert]:
        """
        Check a single incident for SLA compliance.

        Args:
            incident_id: Incident to check.
            org_id: Organisation ID.
            priority: Incident priority (1-5).
            dispatch_time: When dispatch was initiated.
            current_time: Override for current time (testing).

        Returns:
            List of alerts generated (may be empty).
        """
        ...

    async def get_active_alerts(
        self,
        org_id: str,
        severity: Optional[AlertSeverity] = None,
        status: Optional[AlertStatus] = None,
    ) -> list[Alert]:
        """
        Get active alerts for an organization.

        Args:
            org_id: Organisation to query.
            severity: Optional severity filter.
            status: Optional status filter.

        Returns:
            List of matching alerts.
        """
        ...

    async def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str,
        note: Optional[str] = None,
    ) -> Alert:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert to acknowledge.
            user_id: User performing the acknowledgment.
            note: Optional note.

        Returns:
            Updated alert.

        Raises:
            KeyError: If alert not found.
            ValueError: If alert already resolved.
        """
        ...

    async def resolve_alert(
        self,
        alert_id: str,
        user_id: str,
        resolution_note: str,
    ) -> Alert:
        """
        Resolve an alert.

        Args:
            alert_id: Alert to resolve.
            user_id: User resolving the alert.
            resolution_note: Required note explaining resolution.

        Returns:
            Updated alert.
        """
        ...


class EscalationManager:
    """Manages alert escalation according to policies."""

    def __init__(
        self,
        monitor: SLAMonitorService,
        notification_callback: Optional[Callable[[Alert, EscalationLevel], None]] = None,
    ) -> None:
        """
        Initialize the escalation manager.

        Args:
            monitor: The SLA monitor service.
            notification_callback: Called when escalation notifications are sent.
        """
        ...

    def set_policy(self, org_id: str, policy: EscalationPolicy) -> None:
        """
        Set the escalation policy for an organization.

        Args:
            org_id: Organisation ID.
            policy: The escalation policy to apply.
        """
        ...

    def get_policy(self, org_id: str) -> Optional[EscalationPolicy]:
        """
        Get the escalation policy for an organization.

        Args:
            org_id: Organisation ID.

        Returns:
            Policy if set, None otherwise.
        """
        ...

    async def check_escalations(self) -> list[Alert]:
        """
        Check all open alerts for escalation.

        Returns:
            List of alerts that were escalated.
        """
        ...

    async def escalate_alert(
        self,
        alert_id: str,
        reason: str = "timeout",
    ) -> Alert:
        """
        Manually escalate an alert to the next level.

        Args:
            alert_id: Alert to escalate.
            reason: Reason for escalation.

        Returns:
            Updated alert.

        Raises:
            KeyError: If alert not found.
            ValueError: If already at max escalation.
        """
        ...


class AlertSuppressionManager:
    """Manages alert suppression windows and rules."""

    def __init__(self) -> None:
        """Initialize the suppression manager."""
        ...

    def add_suppression(
        self,
        org_id: str,
        rule_pattern: str,
        duration_minutes: int,
        reason: str,
        created_by: str,
    ) -> str:
        """
        Add a temporary alert suppression.

        Args:
            org_id: Organisation to suppress alerts for.
            rule_pattern: Regex pattern matching rule IDs to suppress.
            duration_minutes: How long to suppress.
            reason: Reason for suppression.
            created_by: User creating the suppression.

        Returns:
            Suppression ID.
        """
        ...

    def is_suppressed(self, org_id: str, rule_id: str) -> bool:
        """
        Check if a rule is currently suppressed.

        Args:
            org_id: Organisation ID.
            rule_id: Rule ID to check.

        Returns:
            True if suppressed, False otherwise.
        """
        ...

    def remove_suppression(self, suppression_id: str) -> bool:
        """
        Remove a suppression early.

        Args:
            suppression_id: ID of suppression to remove.

        Returns:
            True if removed, False if not found or expired.
        """
        ...

    def get_active_suppressions(self, org_id: str) -> list[dict[str, Any]]:
        """
        Get all active suppressions for an organization.

        Args:
            org_id: Organisation to query.

        Returns:
            List of active suppression records.
        """
        ...
```

### Required Models/Data Structures

- `AlertRule`: Configuration for when to generate alerts
- `Alert`: A generated alert instance with full lifecycle
- `EscalationPolicy`: Defines escalation chain
- `SLAViolation`: Details of a compliance violation
- `AlertSeverity` / `AlertStatus` / `EscalationLevel`: Status enums

### Architectural Requirements

1. **Async Background Loop**: Use `asyncio` for the monitoring loop, similar to patterns in existing services
2. **Thread Safety**: Protect rule and alert storage with locks for concurrent access
3. **SLA Integration**: Reference `SLA_BY_SEVERITY` from `ionveil/models.py` and `services/compliance/sla.py`
4. **Audit Trail**: Record all alert state changes for compliance, following `AuditLogger` pattern
5. **Notification Abstraction**: Use callback pattern for notifications to decouple from channels
6. **Policy Engine Alignment**: Align severity levels with `ionveil/policy.py` policy states

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/alerts_test.py`):
   - Test rule creation and validation
   - Test SLA threshold calculations
   - Test alert lifecycle (create, acknowledge, resolve)
   - Test suppression logic
   - Test escalation level transitions

2. **Integration Tests** (create `tests/integration/alerts_flow_test.py`):
   - Test end-to-end alert flow from SLA check to notification
   - Test escalation timing
   - Test concurrent alert handling
   - Test integration with existing SLAMonitor from `services/compliance/sla.py`

3. **Coverage Requirements**:
   - Minimum 85% line coverage
   - All alert state transitions must be tested

4. **Contract Validation**:
   - Add service definition to `shared/contracts/contracts.py`:
     ```python
     "alerts": {
         "id": "alerts",
         "port": 8112,
         "health": "/health",
         "description": "SLA monitoring and alerting service",
         "deps": ["policy", "notifications", "audit"],
     }
     ```

---

## General Implementation Notes

### Code Style

- Follow PEP 8 and existing codebase conventions
- Use `from __future__ import annotations` for forward references
- Prefer explicit type hints for all public methods
- Use docstrings following NumPy/Google style as seen in existing modules

### Testing Patterns

- Use `unittest` framework consistent with `tests/run_all.py`
- Create test fixtures in `tests/test_helper.py` if reusable
- Follow naming convention: `*_test.py` for test files
- Use `setattr()` pattern for generating large test suites if needed

### Service Registration

After implementing each service, update `shared/contracts/contracts.py`:
1. Add the service definition to `SERVICE_CONTRACTS`
2. Ensure the port number is unique (8110, 8111, 8112 reserved for these tasks)
3. Run `topological_order()` to verify dependency graph is acyclic

### Integration Points

| New Service | Integrates With |
|-------------|-----------------|
| Policy Simulator | `ionveil/policy.py`, `PolicyEngine` |
| Dashboard Backend | `ionveil/statistics.py`, `services/analytics/metrics.py` |
| SLA Alerting | `ionveil/models.py`, `services/compliance/sla.py`, `services/notifications/channels.py` |
