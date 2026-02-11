# AetherOps - Alternative Tasks

## Overview

The AetherOps orbital operations platform supports five alternative engineering challenges beyond the core bug-fixing task. These tasks exercise feature development, refactoring, performance optimization, API extension, and architectural migration skills using the same codebase.

## Environment

- **Language**: Python
- **Infrastructure**: PostgreSQL, Redis, NATS
- **Difficulty**: Hyper-Principal (3-5 days expected)

## Tasks

### Task 1: Adaptive Rate Limiting with Burst Handling (Feature Development)

Enhance the `RateLimiter` class with Token Bucket algorithm and Sliding Window Counter strategies. Production workloads require sophisticated traffic shaping to allow legitimate burst traffic from monitoring agents while preventing sustained abuse. Implement dynamic adjustment based on queue health metrics: tighten limits by 50% when queue utilization exceeds 80%, relax when it drops below 40%.

**Acceptance Criteria:**
- Token bucket rate limiter with configurable burst_capacity and refill_rate
- Sliding window rate limiter tracking requests across overlapping time windows
- Dynamic adjustment integrating with queue_health() utilization metrics
- Backward compatibility with existing RateLimiter.allow() API
- Serializable state for persistence across restarts
- 100% branch coverage with unit tests

### Task 2: Circuit Breaker State Machine Consolidation (Refactoring)

Consolidate inconsistent circuit breaker implementations across AetherOps services using a proper state machine pattern. Currently, the core `CircuitBreaker` uses simple string-based states while services duplicate divergent implementations with varying threshold logic. Extract failure detection into a pluggable strategy pattern, allowing custom failure criteria (HTTP status codes, exception types, latency thresholds) while sharing canonical state machine logic.

**Acceptance Criteria:**
- Single CircuitBreakerStateMachine class with explicit State enum (CLOSED, OPEN, HALF_OPEN)
- Configurable state transition policies (failure_threshold, success_threshold, reset_timeout)
- FailureDetector protocol for pluggable failure classification
- State transitions emit events for telemetry integration
- Half-open state with configurable probe_count for decision logic
- All service usages migrated to new implementation with no behavioral changes
- Comprehensive edge case coverage

### Task 3: Telemetry Downsampling Pipeline Optimization (Performance Optimization)

Optimize the high-frequency telemetry downsampling pipeline that processes 100,000+ data points during peak bursts. Current profiling shows 40% CPU time spent in `downsample()` and `aggregate_telemetry_window()` functions due to multiple iterations and intermediate list allocations. Implement a streaming aggregator using Welford's online algorithm for numerically stable single-pass computation of downsampled values, running statistics, and anomaly detection.

**Acceptance Criteria:**
- Single-pass streaming aggregator computing downsampled values, mean, variance, and anomaly indices
- Welford's online algorithm for numerically stable variance computation
- 80% reduction in memory allocations (verified via tracemalloc profiling)
- 3x throughput improvement for 10,000+ point windows (verified via benchmark)
- Output identical to original implementation for all test cases
- Support for incremental updates without reprocessing entire window
- Configurable aggregation functions (mean, median, min, max, last)
- No external dependencies beyond Python standard library

### Task 4: GraphQL Telemetry Query API (API Extension)

Implement a unified GraphQL API for telemetry queries that consolidates service-specific REST endpoints scattered across analytics, reporting, and orbit services. Operations teams need flexible exploration without backend changes for each dashboard widget. Support temporal filtering with ISO 8601 timezone-aware ranges, query-time downsampling, cross-service correlation by timestamp, and complexity limits to prevent expensive queries from impacting stability.

**Acceptance Criteria:**
- GraphQL schema defining Telemetry, StatisticalSummary, Anomaly, and TimeRange types
- Query resolvers integrating with statistics.percentile, statistics.variance, telemetry.detect_drift
- ISO 8601 datetime filtering with timezone awareness
- Query-time downsampling leveraging existing telemetry.downsample
- Cross-service correlation joining telemetry streams by timestamp within configurable tolerance
- Query complexity scoring rejecting high-cost queries
- Subscription support for streaming results with configurable batch sizes
- JWT authentication validation from identity service

### Task 5: Event Sourcing Migration for Workflow State (Migration)

Migrate workflow state management from ephemeral instance variables to an event sourcing architecture. Current design loses state on restart and diverges across replicas, causing duplicate executions and orphaned workflows. Persist all state changes as immutable events, supporting temporal queries ("what was state at timestamp X?") for debugging and audit purposes. Maintain backward compatibility: existing workflows snapshot current state, new workflows are fully event-sourced.

**Acceptance Criteria:**
- WorkflowEvent base class with subtypes: WorkflowCreated, StepStarted, StepCompleted, StepFailed, WorkflowCompleted
- EventStore interface with append(event), get_events(workflow_id), get_events_since(timestamp) methods
- WorkflowProjection rebuilds current state from event sequence
- Snapshot events capture migration-time workflow state
- Temporal queries return projected state at any historical timestamp
- Replay validation using resilience.replay_converges() for consistency checks
- Event versioning supporting schema evolution with upcasters
- Integration tests verifying state consistency across service restarts

## Getting Started

Run the test suite to verify your implementation:

```bash
python tests/run_all.py
```

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
