# AetherOps - Greenfield Implementation Tasks

## Overview

The AetherOps platform includes three greenfield modules to implement from scratch. Each task requires building a complete module with service integration, comprehensive unit tests, and integration tests. These implementations test architecting new services within an existing microservices ecosystem.

## Environment

- **Language**: Python
- **Infrastructure**: PostgreSQL, Redis, NATS
- **Difficulty**: Hyper-Principal (3-5 days expected)

## Tasks

### Task 1: Incident Correlation Engine (Greenfield)

Create an incident correlation engine that automatically groups related alerts into incident clusters based on temporal proximity, satellite subsystems, and causal relationships. The engine reduces alert fatigue by consolidating cascading failures into unified incident records.

**Module Location:**
```
aetherops/correlation.py
services/correlation/__init__.py
services/correlation/service.py
```

**Key Interfaces:**

- `Alert` - Immutable alert record with satellite_id, subsystem, severity, timestamp
- `IncidentCluster` - Mutable cluster aggregating related alerts with root_cause tracking
- `CorrelationEngine` - Main orchestrator ingesting alerts and managing cluster lifecycle

**Core Methods:**

- `ingest(alert) -> str` - Process new alert, return assigned cluster_id
- `get_cluster(cluster_id) -> Optional[IncidentCluster]` - Retrieve cluster by ID
- `get_active_clusters() -> List[IncidentCluster]` - Return clusters active within time window
- `close_cluster(cluster_id) -> bool` - Mark cluster as resolved
- `identify_root_cause(cluster_id) -> Optional[str]` - Analyze alerts to find probable root cause using temporal ordering and subsystem dependency graph
- `correlation_score(alert_a, alert_b) -> float` - Compute similarity (0.0-1.0) based on temporal proximity, same satellite, related subsystems, and severity

**Acceptance Criteria:**

- `ingest()` creates new cluster or merges with existing one based on temporal window and subsystem relationships
- Temporal correlation: alerts within configurable time_window_s (default 300s) automatically group
- Temporal gap: alerts outside window create separate clusters
- Subsystem dependency graph determines relationship strength (e.g., power failures cascade to thermal/propulsion)
- Same satellite bonus: +0.3 correlation score for alerts from same satellite
- Root cause identification: first alert in causal chain identified as root cause
- `deduplicate_alerts()` removes duplicate alerts from same satellite/subsystem within 60-second window
- `duration_seconds()` computed from earliest to latest alert in cluster
- `is_multi_satellite()` returns true if cluster affects multiple satellites
- Minimum 90% line coverage for `aetherops/correlation.py`

**Test Files:**
- `tests/unit/correlation_test.py` - Unit tests for correlation logic, temporal grouping, subsystem relationships, root cause identification
- `tests/integration/correlation_flow_test.py` - Integration with NotificationsService, PolicyService, state persistence

### Task 2: Runbook Automation Service (Greenfield)

Create a runbook automation service that executes predefined remediation procedures when specific incident conditions are met. The service supports step-by-step execution, rollback on failure, approval gates for destructive actions, and comprehensive audit logging.

**Module Location:**
```
aetherops/runbook.py
services/runbook/__init__.py
services/runbook/service.py
```

**Key Interfaces:**

- `RunbookStep` - Single executable step with parameters, optional approval gate, timeout, and rollback action
- `Runbook` - Collection of ordered steps with trigger conditions (severity, subsystem, satellite filters)
- `ExecutionContext` - Runtime state tracking execution progress, variables, and audit log
- `StepStatus` - Enum with states: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED, AWAITING_APPROVAL, ROLLED_BACK
- `RunbookStatus` - Enum with states: DRAFT, ACTIVE, RUNNING, COMPLETED, FAILED, ROLLED_BACK

**Core Methods:**

- `register_action(action_name, handler) -> None` - Register callable handler for action type
- `register_runbook(runbook) -> None` - Register runbook, validate all steps have registered handlers
- `get_runbook(runbook_id) -> Optional[Runbook]` - Retrieve runbook by ID
- `find_matching_runbooks(incident_data) -> List[Runbook]` - Find runbooks matching trigger conditions
- `start_execution(runbook_id, triggered_by, variables) -> ExecutionContext` - Start runbook execution
- `execute_next_step(execution_id) -> StepStatus` - Execute next pending step in sequence
- `approve_step(execution_id, step_id, approver) -> bool` - Approve step awaiting approval
- `rollback_execution(execution_id) -> int` - Roll back all completed steps in reverse order
- `get_execution_status(execution_id) -> Optional[Dict]` - Return execution status with all step statuses

**Helper Functions:**

- `validate_runbook(runbook) -> List[str]` - Check for validation errors (at least one step, unique step_ids, positive timeouts, rollback actions)
- `match_conditions(conditions, data) -> bool` - Flexible condition matching supporting exact match, list membership, comparison operators ($lt, $gt, etc.), and logical operators ($and, $or)

**Acceptance Criteria:**

- Runbook registration and retrieval by ID
- Action handler registration and validation
- Execution context creation with initial state
- Successful step execution with status transition
- Step failure handling without crashing execution
- Approval gates pause execution until approver provides consent
- Approval advances to next step
- Single-step rollback executes rollback_action and reverses state
- Multi-step rollback executes all rollback_actions in reverse order
- Exact match conditions ({"severity": 5})
- Comparison operator conditions ({"fuel_kg": {"$lt": 50}})
- Logical operator conditions ({"$and": [...]}, {"$or": [...]})
- Runbook validation detects missing steps, duplicate step_ids, invalid timeouts
- Audit log captures all state transitions with timestamp and actor
- Minimum 90% line coverage for `aetherops/runbook.py`

**Test Files:**
- `tests/unit/runbook_test.py` - Unit tests for registration, execution, approval gates, rollback, condition matching, validation
- `tests/integration/runbook_flow_test.py` - End-to-end runbook triggered by incident, integration with AuditService and SecurityService

### Task 3: Capacity Planning Predictor (Greenfield)

Create a capacity planning module that forecasts satellite resource exhaustion (fuel, power, storage, bandwidth) based on historical telemetry and scheduled mission activities. The predictor identifies satellites at risk and recommends proactive interventions.

**Module Location:**
```
aetherops/capacity.py
services/capacity/__init__.py
services/capacity/service.py
```

**Key Interfaces:**

- `ResourceType` - Enum: FUEL, POWER, STORAGE, BANDWIDTH
- `RiskLevel` - Enum: NOMINAL (safe), WATCH (30-60 days), WARNING (14-30 days), CRITICAL (<14 days)
- `ResourceSnapshot` - Immutable point-in-time measurement (satellite_id, resource_type, timestamp, value, unit)
- `ConsumptionRate` - Computed trend (satellite_id, resource_type, rate_per_day, confidence, sample_period_days)
- `ExhaustionForecast` - Prediction (satellite_id, resource_type, current_value, predicted_exhaustion_date, days_remaining, risk_level, confidence, recommended_action)
- `MissionScheduleEntry` - Scheduled activity (mission_id, satellite_id, start_time, end_time, resource_impacts)

**Core Methods:**

- `ingest_snapshot(snapshot) -> None` - Ingest single resource measurement
- `ingest_snapshots(snapshots) -> int` - Bulk ingest, return count successfully ingested
- `add_scheduled_mission(entry) -> None` - Add scheduled mission with resource impacts
- `compute_consumption_rate(satellite_id, resource_type) -> Optional[ConsumptionRate]` - Compute average consumption from historical data using linear regression
- `forecast_exhaustion(satellite_id, resource_type) -> Optional[ExhaustionForecast]` - Predict exhaustion combining current level, historical rate, scheduled missions, and confidence
- `get_fleet_risk_summary() -> Dict[RiskLevel, List[str]]` - Return all satellites grouped by risk level
- `get_critical_forecasts(max_days) -> List[ExhaustionForecast]` - Get forecasts predicting exhaustion within max_days, sorted by urgency
- `recommend_interventions(satellite_id) -> List[Dict]` - Generate recommendations (reduce burns, decrease duty cycle, purge storage, prioritize communication)

**Helper Functions:**

- `linear_regression(x_values, y_values) -> Tuple[float, float, float]` - Compute (slope, intercept, r_squared) for trend analysis
- `classify_risk_level(days_remaining) -> RiskLevel` - Classify risk based on days to exhaustion
- `interpolate_value(snapshots, target_time) -> Optional[float]` - Linear interpolation between surrounding snapshots
- `aggregate_mission_impact(entries, satellite_id, resource_type, start_date, end_date) -> float` - Sum resource impact from scheduled missions in time range

**Acceptance Criteria:**

- Single snapshot ingestion tracks resource measurements
- Bulk ingestion with return count of successful ingestions
- Linear regression computes consumption rate from historical data
- Insufficient data handled gracefully (returns None)
- Basic exhaustion forecast using current level and consumption rate
- Forecast incorporates scheduled mission impacts
- Risk levels classified correctly: NOMINAL, WATCH, WARNING, CRITICAL
- Fleet-wide risk aggregation groups satellites by level
- Critical forecast filtering and sorting by urgency
- Linear regression math correct (slope, intercept, r_squared)
- Value interpolation using linear interpolation between points
- Mission impact summation for time range
- Intervention recommendations generated for fuel, power, storage, bandwidth
- Minimum 90% line coverage for `aetherops/capacity.py`

**Test Files:**
- `tests/unit/capacity_test.py` - Unit tests for snapshot ingestion, consumption rate, exhaustion forecast, risk classification, linear regression, interpolation, mission impact
- `tests/integration/capacity_flow_test.py` - Integration with TelemetryService, PlannerService, NotificationsService

## Getting Started

Run the test suite to verify your implementation:

```bash
python tests/run_all.py
```

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
