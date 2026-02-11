# NimbusFlow - Greenfield Tasks

## Overview

NimbusFlow supports three greenfield implementation tasks that require building new modules from scratch while following existing architectural patterns. These tasks test system design skills by implementing workflow debugging, cost attribution, and deployment rollback capabilities.

## Environment

- **Language**: Kotlin 1.9
- **Infrastructure**: Maven-based build with JUnit 5 tests, Docker support
- **Difficulty**: Hyper-Principal (70-140h)

## Tasks

### Task 1: Workflow Debugger Service (Greenfield)

Implement a `WorkflowDebuggerService` that provides runtime inspection and tracing capabilities for workflow executions. The service must record trace steps, aggregate bottleneck analysis, and diagnose failed transitions through a thread-safe interface using `ReentrantLock`. The debugger integrates with existing state transition validation to identify workflow pathology.

**Key Interfaces:**
- `WorkflowDebuggerService` - Main interface for trace lifecycle, bottleneck analysis, and failure diagnostics
- `TraceStep` - Individual transition records with timing metadata
- `WorkflowTrace` - Aggregated execution trace for an entity
- `BottleneckAnalysis` - State performance metrics

**Minimum test count:** 15 unit tests

### Task 2: Cost Attribution Engine (Greenfield)

Implement a `CostAttributionEngine` that tracks, allocates, and reports operational costs across dispatch orders, routes, and berth allocations. The engine must calculate fuel costs, delay penalties, and generate period-based cost reports with category and cost center breakdowns. Thread-safe cost recording supports batch operations and duplicate detection.

**Key Interfaces:**
- `CostAttributionEngine` - Main interface for cost tracking and reporting
- `CostLineItem` - Individual cost records with category classification
- `CostCategory` - Enum for fuel, port fees, berth, handling, delay penalties, overhead
- `OrderCostAllocation` - Aggregated cost per order with cost center assignment
- `CostAttributionReport` - Period-based report with category and driver breakdowns

**Minimum test count:** 20 unit tests

### Task 3: Deployment Rollback Manager (Greenfield)

Implement a `RollbackManagerService` that manages deployment versions, tracks rollback history, and enables safe rollback operations. The manager validates rollback eligibility, prevents protected services from rolling back, and calculates health scores based on recent checks. Thread-safe version registration automatically deactivates previous active versions.

**Key Interfaces:**
- `RollbackManagerService` - Main interface for version lifecycle and rollback orchestration
- `DeploymentVersion` - Version metadata with health and configuration information
- `RollbackRecord` - Audit trail of rollback operations
- `RollbackStatus` - Enum for pending, in-progress, completed, failed states
- `RollbackEligibility` - Result of rollback possibility check with blocking reasons
- `HealthCheckResult` - Deployment health metrics with latency and error rates

**Minimum test count:** 25 unit tests

## Getting Started

```bash
./gradlew test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md):

- Workflow Debugger: Trace lifecycle, bottleneck analysis, concurrent safety, 15+ tests
- Cost Attribution: Cost tracking, allocation, reporting, SLA integration, 20+ tests
- Rollback Manager: Version management, rollback lifecycle, health scoring, 25+ tests

All public methods and code paths must have test coverage. Services must follow existing patterns: `ReentrantLock` for synchronization, companion objects or singletons for registry, and Kotlin idioms for data classes and immutable returns.
