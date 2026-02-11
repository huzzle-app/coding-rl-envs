# AetherOps Greenfield Tasks

This document defines new modules to be implemented from scratch for the AetherOps orbital operations platform. Each task requires creating a new service/module that integrates with the existing architecture.

---

## Task 1: Incident Correlation Engine

### Overview

Create an incident correlation engine that automatically groups related alerts and incidents based on temporal proximity, satellite subsystems, and causal relationships. The engine should reduce alert fatigue by consolidating cascading failures into unified incident clusters.

### Module Location

```
aetherops/correlation.py
services/correlation/__init__.py
services/correlation/service.py
```

### Python Interface Contract

```python
# aetherops/correlation.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class Alert:
    """Raw alert from telemetry or monitoring systems."""
    alert_id: str
    satellite_id: str
    subsystem: str
    severity: int
    timestamp: datetime
    message: str
    metric_value: Optional[float] = None


@dataclass
class IncidentCluster:
    """Group of correlated alerts representing a single incident."""
    cluster_id: str
    root_cause_alert_id: Optional[str]
    alert_ids: Set[str] = field(default_factory=set)
    affected_satellites: Set[str] = field(default_factory=set)
    affected_subsystems: Set[str] = field(default_factory=set)
    max_severity: int = 1
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def duration_seconds(self) -> float:
        """Return duration of incident cluster in seconds."""
        ...

    def is_multi_satellite(self) -> bool:
        """Return True if incident affects multiple satellites."""
        ...


class CorrelationEngine:
    """
    Correlates alerts into incident clusters based on temporal proximity,
    subsystem relationships, and satellite locality.
    """

    def __init__(
        self,
        time_window_s: int = 300,
        subsystem_graph: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """
        Initialize the correlation engine.

        Args:
            time_window_s: Maximum time gap between related alerts (default 5 min)
            subsystem_graph: Directed graph of subsystem dependencies
                             (e.g., {"power": ["thermal", "propulsion"]})
        """
        ...

    def ingest(self, alert: Alert) -> str:
        """
        Ingest a new alert and return the cluster_id it was assigned to.
        May create a new cluster or merge with existing one.

        Args:
            alert: The alert to ingest

        Returns:
            The cluster_id the alert was assigned to
        """
        ...

    def get_cluster(self, cluster_id: str) -> Optional[IncidentCluster]:
        """Return the incident cluster by ID, or None if not found."""
        ...

    def get_active_clusters(self) -> List[IncidentCluster]:
        """
        Return all clusters that haven't been closed.
        Clusters are considered active if they received an alert
        within the time window.
        """
        ...

    def close_cluster(self, cluster_id: str) -> bool:
        """
        Mark a cluster as resolved. Returns True if cluster existed.
        """
        ...

    def identify_root_cause(self, cluster_id: str) -> Optional[str]:
        """
        Analyze alerts in a cluster to identify the probable root cause.
        Uses temporal ordering and subsystem dependency graph.

        Returns:
            The alert_id of the probable root cause, or None if undetermined
        """
        ...

    def correlation_score(self, alert_a: Alert, alert_b: Alert) -> float:
        """
        Compute correlation score between two alerts (0.0 to 1.0).
        Higher score means more likely to be related.

        Factors:
        - Temporal proximity (exponential decay with time difference)
        - Same satellite (+0.3)
        - Related subsystems via dependency graph (+0.2)
        - Similar severity (+0.1)
        """
        ...


def build_subsystem_graph() -> Dict[str, List[str]]:
    """
    Return the default subsystem dependency graph for orbital operations.

    Example relationships:
    - power failures can cause thermal and propulsion issues
    - communication failures can cascade to telemetry
    - attitude control affects pointing and propulsion
    """
    ...


def deduplicate_alerts(alerts: List[Alert], window_s: int = 60) -> List[Alert]:
    """
    Remove duplicate alerts from the same satellite/subsystem within window.
    Keeps the first occurrence.

    Args:
        alerts: List of alerts to deduplicate
        window_s: Time window for considering duplicates

    Returns:
        Deduplicated list of alerts
    """
    ...
```

### Required Models/Data Structures

1. `Alert` - Immutable alert record with satellite, subsystem, severity, timestamp
2. `IncidentCluster` - Mutable cluster aggregating related alerts
3. Subsystem dependency graph as `Dict[str, List[str]]`

### Architectural Patterns to Follow

- Use `@dataclass(frozen=True)` for immutable value objects (like `Alert`)
- Use `@dataclass` with mutable fields for stateful objects (like `IncidentCluster`)
- Service layer in `services/correlation/service.py` following existing service patterns
- Constants at module level (e.g., `DEFAULT_TIME_WINDOW_S = 300`)
- Type hints on all public methods
- Docstrings for all public classes and methods

### Acceptance Criteria

**Unit Tests** (in `tests/unit/correlation_test.py`):
- [ ] `test_single_alert_creates_cluster` - Ingesting one alert creates a new cluster
- [ ] `test_temporal_correlation` - Alerts within time window join same cluster
- [ ] `test_temporal_gap_creates_new_cluster` - Alerts outside window create separate clusters
- [ ] `test_subsystem_dependency_correlation` - Related subsystems correlate
- [ ] `test_same_satellite_bonus` - Same satellite alerts get higher correlation score
- [ ] `test_root_cause_identification` - First alert in causal chain identified as root cause
- [ ] `test_deduplicate_alerts` - Duplicate removal works correctly
- [ ] `test_cluster_duration_calculation` - Duration computed correctly
- [ ] `test_multi_satellite_detection` - Multi-satellite incidents flagged
- [ ] `test_close_cluster` - Closing clusters removes from active list

**Integration Tests** (in `tests/integration/correlation_flow_test.py`):
- [ ] Integration with `NotificationsService` for escalation
- [ ] Integration with `PolicyService` for severity-based routing
- [ ] Correlation engine state persists across service restarts (mock)

**Coverage Requirements**:
- Minimum 90% line coverage for `aetherops/correlation.py`
- All public methods must have at least one test

---

## Task 2: Runbook Automation Service

### Overview

Create a runbook automation service that executes predefined remediation procedures when specific incident conditions are met. The service should support step-by-step execution, rollback on failure, approval gates for destructive actions, and audit logging.

### Module Location

```
aetherops/runbook.py
services/runbook/__init__.py
services/runbook/service.py
```

### Python Interface Contract

```python
# aetherops/runbook.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"
    ROLLED_BACK = "rolled_back"


class RunbookStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RunbookStep:
    """A single step in a runbook procedure."""
    step_id: str
    name: str
    action: str  # Action identifier (e.g., "restart_service", "scale_down")
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    timeout_s: int = 300
    rollback_action: Optional[str] = None
    rollback_parameters: Optional[Dict[str, Any]] = None
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class Runbook:
    """A remediation procedure consisting of ordered steps."""
    runbook_id: str
    name: str
    description: str
    trigger_conditions: Dict[str, Any]  # Conditions that trigger this runbook
    steps: List[RunbookStep] = field(default_factory=list)
    status: RunbookStatus = RunbookStatus.DRAFT
    created_by: str = "system"
    created_at: Optional[datetime] = None


@dataclass
class ExecutionContext:
    """Runtime context for runbook execution."""
    execution_id: str
    runbook_id: str
    triggered_by: str  # alert_id, user_id, or "scheduled"
    satellite_id: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step_index: int = 0
    audit_log: List[Dict[str, Any]] = field(default_factory=list)


# Type alias for action handlers
ActionHandler = Callable[[RunbookStep, ExecutionContext], bool]


class RunbookEngine:
    """
    Executes runbooks with step-by-step execution, rollback support,
    and approval gates.
    """

    def __init__(self) -> None:
        """Initialize the runbook engine with empty registries."""
        ...

    def register_action(self, action_name: str, handler: ActionHandler) -> None:
        """
        Register an action handler that executes a specific action type.

        Args:
            action_name: The action identifier (e.g., "restart_service")
            handler: Function that executes the action, returns True on success
        """
        ...

    def register_runbook(self, runbook: Runbook) -> None:
        """
        Register a runbook definition. Validates steps have registered actions.

        Raises:
            ValueError: If runbook has steps with unregistered actions
        """
        ...

    def get_runbook(self, runbook_id: str) -> Optional[Runbook]:
        """Return runbook by ID or None if not found."""
        ...

    def find_matching_runbooks(
        self, incident_data: Dict[str, Any]
    ) -> List[Runbook]:
        """
        Find all runbooks whose trigger_conditions match the incident data.

        Args:
            incident_data: Dict containing incident attributes to match against

        Returns:
            List of matching runbooks, sorted by specificity (most specific first)
        """
        ...

    def start_execution(
        self,
        runbook_id: str,
        triggered_by: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> ExecutionContext:
        """
        Start executing a runbook. Returns the execution context.

        Args:
            runbook_id: The runbook to execute
            triggered_by: ID of the trigger (alert_id, user_id, etc.)
            variables: Runtime variables to pass to steps

        Returns:
            ExecutionContext for tracking the execution

        Raises:
            ValueError: If runbook not found or already running
        """
        ...

    def execute_next_step(self, execution_id: str) -> StepStatus:
        """
        Execute the next pending step in the runbook.

        Returns:
            The status of the executed step

        Raises:
            ValueError: If execution not found or no pending steps
        """
        ...

    def approve_step(self, execution_id: str, step_id: str, approver: str) -> bool:
        """
        Approve a step that is awaiting approval.

        Returns:
            True if approval was recorded, False if step not awaiting approval
        """
        ...

    def rollback_execution(self, execution_id: str) -> int:
        """
        Roll back all completed steps in reverse order.

        Returns:
            Number of steps successfully rolled back
        """
        ...

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of an execution including all step statuses.
        """
        ...


def validate_runbook(runbook: Runbook) -> List[str]:
    """
    Validate a runbook definition and return list of validation errors.

    Checks:
    - At least one step defined
    - All step_ids are unique
    - timeout_s is positive
    - rollback_action defined if step is destructive
    """
    ...


def match_conditions(
    conditions: Dict[str, Any], data: Dict[str, Any]
) -> bool:
    """
    Check if incident data matches trigger conditions.

    Supports:
    - Exact match: {"severity": 5}
    - List membership: {"subsystem": ["power", "thermal"]}
    - Comparison: {"fuel_kg": {"$lt": 50}}
    - Logical operators: {"$and": [...], "$or": [...]}

    Args:
        conditions: The trigger conditions to match
        data: The incident data to check

    Returns:
        True if all conditions are satisfied
    """
    ...
```

### Required Models/Data Structures

1. `RunbookStep` - Single executable step with rollback support
2. `Runbook` - Collection of steps with trigger conditions
3. `ExecutionContext` - Runtime state for a runbook execution
4. `StepStatus` and `RunbookStatus` enums for state tracking
5. `ActionHandler` type alias for step executors

### Architectural Patterns to Follow

- Use `Enum` for status values (following `aetherops/workflow.py` patterns)
- Audit log as list of dicts with timestamp, action, actor fields
- Action handlers registered via callback pattern
- Condition matching similar to MongoDB query operators
- Service should integrate with `AuditService` for logging

### Acceptance Criteria

**Unit Tests** (in `tests/unit/runbook_test.py`):
- [ ] `test_register_runbook` - Runbook registration and retrieval
- [ ] `test_register_action` - Action handler registration
- [ ] `test_start_execution` - Execution context creation
- [ ] `test_execute_step_success` - Successful step execution
- [ ] `test_execute_step_failure` - Step failure handling
- [ ] `test_approval_gate` - Steps requiring approval pause execution
- [ ] `test_approve_step` - Approval advances execution
- [ ] `test_rollback_single_step` - Single step rollback
- [ ] `test_rollback_multiple_steps` - Multi-step rollback in reverse order
- [ ] `test_condition_matching_exact` - Exact match conditions
- [ ] `test_condition_matching_comparison` - Comparison operators
- [ ] `test_condition_matching_logical` - AND/OR operators
- [ ] `test_validate_runbook` - Validation error detection

**Integration Tests** (in `tests/integration/runbook_flow_test.py`):
- [ ] End-to-end runbook triggered by incident
- [ ] Integration with `AuditService` for execution logging
- [ ] Integration with `SecurityService` for approval authorization

**Coverage Requirements**:
- Minimum 90% line coverage for `aetherops/runbook.py`
- All public methods must have at least one test

---

## Task 3: Capacity Planning Predictor

### Overview

Create a capacity planning module that forecasts satellite resource consumption (fuel, power, storage) based on historical telemetry and mission schedules. The predictor should identify satellites at risk of resource exhaustion and recommend proactive interventions.

### Module Location

```
aetherops/capacity.py
services/capacity/__init__.py
services/capacity/service.py
```

### Python Interface Contract

```python
# aetherops/capacity.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ResourceType(Enum):
    FUEL = "fuel"
    POWER = "power"
    STORAGE = "storage"
    BANDWIDTH = "bandwidth"


class RiskLevel(Enum):
    NOMINAL = "nominal"
    WATCH = "watch"       # 30-60 days to exhaustion
    WARNING = "warning"   # 14-30 days to exhaustion
    CRITICAL = "critical" # <14 days to exhaustion


@dataclass(frozen=True)
class ResourceSnapshot:
    """Point-in-time resource measurement."""
    satellite_id: str
    resource_type: ResourceType
    timestamp: datetime
    value: float
    unit: str  # "kg", "kW", "GB", "Mbps"


@dataclass(frozen=True)
class ConsumptionRate:
    """Resource consumption rate over a period."""
    satellite_id: str
    resource_type: ResourceType
    rate_per_day: float
    confidence: float  # 0.0 to 1.0
    sample_period_days: int


@dataclass(frozen=True)
class ExhaustionForecast:
    """Prediction of when a resource will be exhausted."""
    satellite_id: str
    resource_type: ResourceType
    current_value: float
    predicted_exhaustion_date: Optional[datetime]
    days_remaining: Optional[float]
    risk_level: RiskLevel
    confidence: float
    recommended_action: Optional[str] = None


@dataclass
class MissionScheduleEntry:
    """Scheduled mission activity that consumes resources."""
    mission_id: str
    satellite_id: str
    start_time: datetime
    end_time: datetime
    resource_impacts: Dict[ResourceType, float]  # Positive = consumption


class CapacityPredictor:
    """
    Forecasts resource exhaustion based on historical consumption
    and scheduled mission activities.
    """

    def __init__(
        self,
        history_window_days: int = 30,
        forecast_horizon_days: int = 90,
    ) -> None:
        """
        Initialize the capacity predictor.

        Args:
            history_window_days: Days of history to use for trend analysis
            forecast_horizon_days: How far ahead to forecast
        """
        ...

    def ingest_snapshot(self, snapshot: ResourceSnapshot) -> None:
        """
        Ingest a new resource measurement.

        Args:
            snapshot: The resource snapshot to ingest
        """
        ...

    def ingest_snapshots(self, snapshots: List[ResourceSnapshot]) -> int:
        """
        Bulk ingest multiple snapshots.

        Returns:
            Number of snapshots successfully ingested
        """
        ...

    def add_scheduled_mission(self, entry: MissionScheduleEntry) -> None:
        """
        Add a scheduled mission that will impact resource consumption.
        """
        ...

    def compute_consumption_rate(
        self,
        satellite_id: str,
        resource_type: ResourceType,
    ) -> Optional[ConsumptionRate]:
        """
        Compute the average consumption rate from historical data.

        Uses linear regression over the history window to determine
        trend direction and rate.

        Returns:
            ConsumptionRate if sufficient data, None otherwise
        """
        ...

    def forecast_exhaustion(
        self,
        satellite_id: str,
        resource_type: ResourceType,
    ) -> Optional[ExhaustionForecast]:
        """
        Forecast when a resource will be exhausted.

        Combines:
        - Current resource level
        - Historical consumption rate
        - Scheduled mission impacts
        - Confidence interval based on data variance

        Returns:
            ExhaustionForecast or None if insufficient data
        """
        ...

    def get_fleet_risk_summary(self) -> Dict[RiskLevel, List[str]]:
        """
        Get a summary of all satellites grouped by risk level.

        Returns:
            Dict mapping RiskLevel to list of satellite_ids at that level
        """
        ...

    def get_critical_forecasts(
        self,
        max_days: int = 14,
    ) -> List[ExhaustionForecast]:
        """
        Get all forecasts predicting exhaustion within max_days.

        Returns:
            List of critical forecasts sorted by days_remaining ascending
        """
        ...

    def recommend_interventions(
        self,
        satellite_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate intervention recommendations for a satellite.

        Recommendations may include:
        - Reduce scheduled burns (fuel)
        - Decrease duty cycle (power)
        - Purge old data (storage)
        - Prioritize communication windows (bandwidth)

        Returns:
            List of recommendation dicts with action, impact, priority
        """
        ...


def linear_regression(
    x_values: List[float], y_values: List[float]
) -> Tuple[float, float, float]:
    """
    Compute linear regression coefficients.

    Args:
        x_values: Independent variable values
        y_values: Dependent variable values

    Returns:
        Tuple of (slope, intercept, r_squared)

    Raises:
        ValueError: If insufficient data points or lengths don't match
    """
    ...


def classify_risk_level(days_remaining: Optional[float]) -> RiskLevel:
    """
    Classify risk level based on days until resource exhaustion.

    Args:
        days_remaining: Days until exhaustion, None if won't exhaust

    Returns:
        RiskLevel classification
    """
    ...


def interpolate_value(
    snapshots: List[ResourceSnapshot], target_time: datetime
) -> Optional[float]:
    """
    Interpolate resource value at a specific time from surrounding snapshots.

    Uses linear interpolation between the two closest snapshots.

    Args:
        snapshots: Sorted list of snapshots for same satellite/resource
        target_time: Time to interpolate value for

    Returns:
        Interpolated value or None if outside snapshot range
    """
    ...


def aggregate_mission_impact(
    entries: List[MissionScheduleEntry],
    satellite_id: str,
    resource_type: ResourceType,
    start_date: datetime,
    end_date: datetime,
) -> float:
    """
    Sum total resource impact from scheduled missions in a date range.

    Args:
        entries: All mission schedule entries
        satellite_id: Filter to this satellite
        resource_type: Filter to this resource type
        start_date: Start of aggregation window
        end_date: End of aggregation window

    Returns:
        Total resource impact (positive = consumption)
    """
    ...
```

### Required Models/Data Structures

1. `ResourceSnapshot` - Immutable point-in-time measurement
2. `ConsumptionRate` - Computed consumption trend
3. `ExhaustionForecast` - Prediction with confidence and risk level
4. `MissionScheduleEntry` - Scheduled activity with resource impacts
5. `ResourceType` and `RiskLevel` enums

### Architectural Patterns to Follow

- Use `@dataclass(frozen=True)` for immutable measurement data
- Store historical snapshots in sorted order by timestamp
- Linear regression for trend computation (similar to telemetry patterns)
- Risk classification thresholds as module-level constants
- Integration with `PlannerService` for mission schedule data
- Integration with `OrbitService` for burn planning impacts

### Acceptance Criteria

**Unit Tests** (in `tests/unit/capacity_test.py`):
- [ ] `test_ingest_snapshot` - Single snapshot ingestion
- [ ] `test_ingest_snapshots_bulk` - Bulk ingestion
- [ ] `test_consumption_rate_linear` - Linear consumption rate calculation
- [ ] `test_consumption_rate_insufficient_data` - Handles missing data
- [ ] `test_forecast_exhaustion` - Basic exhaustion forecast
- [ ] `test_forecast_with_missions` - Forecast incorporates scheduled missions
- [ ] `test_risk_level_classification` - Risk levels assigned correctly
- [ ] `test_fleet_risk_summary` - Fleet-wide aggregation
- [ ] `test_critical_forecasts` - Filtering by days remaining
- [ ] `test_linear_regression` - Regression math is correct
- [ ] `test_interpolate_value` - Value interpolation between points
- [ ] `test_aggregate_mission_impact` - Mission impact summation
- [ ] `test_recommend_interventions` - Recommendations generated

**Integration Tests** (in `tests/integration/capacity_flow_test.py`):
- [ ] Integration with `TelemetryService` for real-time snapshots
- [ ] Integration with `PlannerService` for mission schedules
- [ ] Integration with `NotificationsService` for risk alerts

**Coverage Requirements**:
- Minimum 90% line coverage for `aetherops/capacity.py`
- All public methods must have at least one test

---

## General Implementation Guidelines

### Directory Structure

```
aetherops/
  __init__.py
  correlation.py      # Task 1
  runbook.py          # Task 2
  capacity.py         # Task 3
  ...existing modules...

services/
  correlation/
    __init__.py
    service.py
  runbook/
    __init__.py
    service.py
  capacity/
    __init__.py
    service.py
  ...existing services...

tests/
  unit/
    correlation_test.py
    runbook_test.py
    capacity_test.py
  integration/
    correlation_flow_test.py
    runbook_flow_test.py
    capacity_flow_test.py
```

### Service Layer Pattern

Each service module should follow the existing pattern:

```python
# services/<name>/service.py
from __future__ import annotations

SERVICE_NAME = "<name>"
SERVICE_ROLE = "<description of service role>"

# Service-specific constants

# Data classes for service state

# Main service class with methods

# Helper functions
```

### Contract Registration

Add new services to `shared/contracts/contracts.py`:

1. Add entry to `SERVICE_SLO` dict with latency and availability targets
2. Add entry to `SERVICE_DEFS` dict with port and dependencies
3. Update `REQUIRED_EVENT_FIELDS` or `REQUIRED_COMMAND_FIELDS` if needed

### Testing Pattern

Follow the existing test structure:

```python
# tests/unit/<module>_test.py
import unittest

from aetherops.<module> import SomeClass, some_function


class SomeClassTest(unittest.TestCase):
    def test_method_behavior(self) -> None:
        # Arrange
        # Act
        # Assert
        pass


if __name__ == "__main__":
    unittest.main()
```
