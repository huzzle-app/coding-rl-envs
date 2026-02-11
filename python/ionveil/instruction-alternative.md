# IonVeil - Alternative Tasks

## Overview

Beyond debugging, these tasks test feature development, refactoring, optimization, API extension, and migration capabilities within the policy enforcement and dispatch domain. Each task requires implementing significant architectural changes while maintaining compatibility with the existing system.

## Environment

- **Language**: Python
- **Infrastructure**: PostgreSQL x3, Redis, NATS
- **Difficulty**: Apex-Principal

## Tasks

### Task 1: Feature Development - Cascading Policy Overrides

Implement a hierarchical policy override system that allows zone-level and agency-level policies to cascade while respecting priority ordering. Currently, policies are applied globally without considering organizational hierarchy. The new system should support policy inheritance where child zones can override parent policies, but only for less restrictive rules.

Key requirements: New `PolicyHierarchy` class manages parent-child policy relationships; Zone policies inherit from parent unless explicitly overridden; Child zones can only escalate (not de-escalate) relative to parent policy; Override audit trail records source, timestamp, and authorization; Automatic override cleanup when parent policy de-escalates; Thread-safe policy resolution for concurrent zone queries.

**Test Command:**
```bash
python tests/run_all.py -k policy_hierarchy
```

### Task 2: Refactoring - Unified Queue Health Monitor

The queue health monitoring logic is currently scattered across `ionveil/queue.py`, `ionveil/statistics.py`, and `services/analytics/metrics.py`, each with slightly different threshold logic and status labels. Extract this into a unified `QueueHealthMonitor` service that provides consistent health assessment across the entire system.

Key requirements: New `QueueHealthMonitor` class in `ionveil/monitoring.py`; All queue health logic consolidated: utilization, wait time estimation, backpressure; Single threshold configuration source with environment variable overrides; Consistent status labels across all monitoring endpoints; Monitor is stateless and injectable for testing; Existing API responses maintain backward compatibility.

**Test Command:**
```bash
python tests/run_all.py -k queue
```

### Task 3: Performance Optimization - Batch Dispatch Planning

The current `plan_dispatch` function processes orders individually, resulting in O(N log N) sorting for every dispatch request. For high-volume periods with 10,000+ pending orders across multiple agencies, this creates dispatch latency spikes exceeding SLA targets. Optimize the dispatch planning to use incremental sorting with a priority heap structure.

Key requirements: Dispatch planning for 10,000 orders completes in under 50ms; New order insertion maintains O(log N) complexity; Batch extraction for multi-agency dispatch in single operation; Order coalescing window configurable (default 100ms); Memory usage under 100MB for 50,000 order pool; Dispatch order priority remains identical to current algorithm.

**Test Command:**
```bash
python tests/run_all.py -k dispatch_performance
```

### Task 4: API Extension - Multi-Channel Route Failover

Add a multi-channel failover API that allows dispatch requests to specify backup routing channels. When the primary channel is blocked or exceeds latency thresholds, the system should automatically attempt the next channel in the failover chain. Currently, dispatchers must manually retry with different channels when primary routing fails.

Key requirements: New endpoint `POST /dispatch/route/failover` accepts primary and backup channel list; Automatic failover when primary channel latency exceeds threshold (configurable); Per-channel circuit breaker integration; Failover attempt logging with channel, latency, and failure reason; Response includes which channel succeeded and failover chain execution summary; Maximum 3 failover attempts per request (configurable).

**Test Command:**
```bash
python tests/run_all.py -k route_failover
```

### Task 5: Migration - Event Sourcing for Workflow State

Migrate the `WorkflowEngine` from direct state mutation to an event-sourced architecture. Currently, entity states are stored directly and history is an append-only log that can diverge from the actual state. The new design should derive current state entirely from the event stream, enabling point-in-time state reconstruction and reliable event replay.

Key requirements: New `WorkflowEventStore` class persists events as the source of truth; Entity state derived from event stream replay; Point-in-time state reconstruction via `get_state_at(entity_id, timestamp)`; Automatic snapshotting for entities exceeding 1000 events; Events include sequence_number, causation_id, and correlation_id; Migration script converts existing state and history to events; All existing workflow tests pass against event-sourced implementation.

**Test Command:**
```bash
python tests/run_all.py -k workflow
```

## Getting Started

```bash
python tests/run_all.py
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
