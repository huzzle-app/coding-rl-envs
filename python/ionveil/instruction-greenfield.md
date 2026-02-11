# IonVeil - Greenfield Tasks

## Overview

Greenfield implementation tasks for the IonVeil policy enforcement and dispatch system. Each task requires implementing a new module from scratch while following the existing architectural patterns found in the codebase. These tasks test infrastructure design, system integration, and end-to-end feature development.

## Environment

- **Language**: Python
- **Infrastructure**: PostgreSQL x3, Redis, NATS
- **Difficulty**: Apex-Principal

## Tasks

### Task 1: Policy Simulator Service

Implement a Policy Simulator that allows operators to test policy changes in a sandboxed environment before deploying them to production. The simulator must accurately model the effects of escalation thresholds, de-escalation rules, and failure bursts on system behavior without affecting live operations.

**Module Location:** `services/simulator/__init__.py` and `services/simulator/engine.py`

**Interface Highlights:**
- `PolicySimulator`: Thread-safe simulator supporting concurrent test runs (max 10 concurrent)
- `PolicyScenario` and `FailurePattern`: Dataclasses defining test configurations
- `SimulationResult`: Complete simulation output with policy transitions, compliance metrics
- `ScenarioBuilder` and `FailurePatternGenerator`: Fluent APIs for test setup
- Support for point-in-time policy state queries and recommendation generation

**Architectural Requirements:**
- Thread Safety: Use `threading.Lock` patterns from `ionveil/policy.py`
- Integration: Must work with existing `PolicyEngine` without modification
- Dataclasses: Use `@dataclass` style from `ionveil/models.py`
- Validation: Input validation similar to `validate_dispatch_order()`

**Test Command:**
```bash
python tests/run_all.py -k simulator
```

### Task 2: Dispatch Analytics Dashboard Backend

Implement a real-time analytics backend that aggregates dispatch metrics, computes KPIs, and provides data for operational dashboards. The service must support time-windowed aggregations, geographic breakdowns, and trend analysis while handling high-throughput event streams.

**Module Location:** `services/dashboard/__init__.py` and `services/dashboard/aggregator.py`

**Interface Highlights:**
- `DispatchAggregator`: Async event ingestion with sliding window aggregations (retention: 24h)
- `DispatchEvent` and `AggregatedMetric`: Data structures for event streaming and metrics
- `DashboardSnapshot`: Complete dashboard state with active/pending dispatch counts
- `TrendAnalyzer`: Trend detection with slope calculation and hourly forecasts
- `GeographicBreakdown`: Regional summaries and heatmap-ready data

**Architectural Requirements:**
- Async Pattern: Use `async/await` consistently from `services/analytics/metrics.py`
- Streaming: Implement `AsyncIterator` for real-time metric subscriptions
- Statistics: Reuse `percentile()`, `mean()`, `moving_average()` from `ionveil/statistics.py`
- Thread Safety: Protect shared buffers with locks when accessed from sync contexts

**Test Command:**
```bash
python tests/run_all.py -k dashboard
```

### Task 3: SLA Monitoring and Alerting Service

Implement a proactive SLA monitoring service that tracks compliance in real-time, generates alerts when SLA breaches are imminent or occur, and provides escalation workflows. The service must integrate with the existing notification channels and maintain an audit trail of all alerts.

**Module Location:** `services/alerts/__init__.py` and `services/alerts/monitor.py`

**Interface Highlights:**
- `SLAMonitorService`: Background monitoring loop with configurable check intervals
- `AlertRule`, `Alert`, `EscalationPolicy`: Full alert lifecycle management (open/acknowledged/resolved/escalated)
- `EscalationManager`: Multi-level escalation chains (L1 Operator → L4 Executive)
- `AlertSuppressionManager`: Temporary suppression windows with regex pattern matching
- Per-alert audit trail with timestamps and user attribution

**Architectural Requirements:**
- Async Background Loop: Use `asyncio` for monitoring, similar to existing async patterns
- Thread Safety: Protect rule and alert storage with locks
- SLA Integration: Reference `SLA_BY_SEVERITY` from `ionveil/models.py` and `services/compliance/sla.py`
- Audit Trail: Record all alert state changes following `AuditLogger` pattern
- Notification Abstraction: Use callback pattern for notifications to decouple from channels

**Test Command:**
```bash
python tests/run_all.py -k alerts
```

## Getting Started

```bash
python tests/run_all.py
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md):

- Complete interface contract implementation with all required classes and methods
- Comprehensive unit and integration test coverage (minimum 85% line coverage)
- Service registration in `shared/contracts/contracts.py` with unique ports (8110, 8111, 8112)
- Full architectural alignment with existing codebase patterns
- Thread-safe and async-aware implementations for production use
