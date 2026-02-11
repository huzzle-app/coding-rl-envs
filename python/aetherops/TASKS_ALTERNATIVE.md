# AetherOps - Alternative Task Specifications

This document contains alternative task specifications for the AetherOps operations platform. Each task represents a different engineering challenge that could be assigned instead of the standard bug-fixing task.

---

## Task 1: Adaptive Rate Limiting with Burst Handling (Feature Development)

### Description

The current `RateLimiter` class in AetherOps provides basic request counting per client, but production workloads require more sophisticated traffic shaping. Operations teams have reported that legitimate burst traffic from monitoring agents and batch telemetry uploads are being incorrectly throttled, while sustained high-volume traffic from misbehaving clients slips through.

Implement an adaptive rate limiting system using the Token Bucket algorithm with configurable burst capacity. The system should allow short bursts of traffic up to a specified burst limit while still enforcing the average rate over time. Additionally, implement a sliding window counter as an alternative strategy that tracks request counts across overlapping time windows for smoother rate enforcement.

The feature must integrate with the existing queue health monitoring to dynamically adjust rate limits based on current system load. When queue utilization exceeds 80%, rate limits should tighten by 50%. When utilization drops below 40%, limits can relax to allow catch-up processing.

### Acceptance Criteria

- Token bucket rate limiter allows burst traffic up to configured burst_capacity tokens
- Tokens replenish at a configurable refill_rate per second
- Sliding window rate limiter tracks requests across configurable window_count overlapping windows
- Rate limiters expose current token/request count for monitoring dashboards
- Dynamic adjustment integrates with queue_health() utilization metrics
- Backward compatibility maintained with existing RateLimiter.allow() API
- Rate limiter state is serializable for persistence across service restarts
- All new functionality covered by unit tests achieving 100% branch coverage

### Test Command

```bash
python tests/run_all.py
```

---

## Task 2: Circuit Breaker State Machine Consolidation (Refactoring)

### Description

The circuit breaker pattern is implemented inconsistently across AetherOps. The core `CircuitBreaker` class in the resilience module uses a simple string-based state ("closed", "open", "half-open"), while several microservices have duplicated and divergent implementations with varying threshold logic, timeout behaviors, and state transition rules.

Refactor the circuit breaker implementation to use a proper state machine pattern with explicit state transitions and configurable policies. The refactored design should provide a single, canonical implementation that all services can adopt. State transitions should emit observable events for integration with the telemetry and analytics pipelines.

The refactoring must address the current tight coupling between failure detection and state management. Extract failure detection into a pluggable strategy pattern, allowing different services to define custom failure criteria (HTTP status codes, exception types, latency thresholds) while sharing the core state machine logic.

### Acceptance Criteria

- Single CircuitBreakerStateMachine class with explicit State enum (CLOSED, OPEN, HALF_OPEN)
- Configurable state transition policies (failure_threshold, success_threshold, reset_timeout)
- FailureDetector protocol/interface for pluggable failure classification
- State transitions emit events compatible with telemetry recording
- Half-open state allows configurable probe_count requests before deciding next state
- All existing CircuitBreaker usages in services migrated to new implementation
- No behavioral changes to external API (allow_request, record_failure, record_success)
- Comprehensive state transition tests covering all edge cases

### Test Command

```bash
python tests/run_all.py
```

---

## Task 3: Telemetry Downsampling Pipeline Optimization (Performance Optimization)

### Description

The telemetry downsampling pipeline processes high-frequency sensor data from orbital assets, reducing data volume before transmission to ground stations. Current profiling shows that the `downsample()` and `aggregate_telemetry_window()` functions are performance bottlenecks, consuming 40% of CPU time during peak telemetry bursts when processing windows of 100,000+ data points.

Optimize the downsampling pipeline for high-throughput scenarios without sacrificing accuracy. The current implementation iterates through values multiple times (once for downsampling, once for anomaly detection, once for summary statistics) when a single pass could compute all required outputs. Additionally, the bucket aggregation within downsample creates many intermediate lists that stress the garbage collector.

Implement a streaming aggregator that computes downsampled values, running statistics (mean, variance), and anomaly flags in a single pass using Welford's online algorithm for numerically stable variance computation. The optimization should maintain identical output for identical input while reducing memory allocations by 80% and improving throughput by at least 3x for windows exceeding 10,000 points.

### Acceptance Criteria

- Single-pass streaming aggregator computes downsampled values, mean, variance, and anomaly indices
- Welford's online algorithm used for numerically stable variance computation
- Memory allocations reduced by 80% (verified via tracemalloc profiling tests)
- Throughput improved by 3x for 10,000+ point windows (verified via benchmark tests)
- Output identical to original implementation for all existing test cases
- Support for incremental updates (add new values without reprocessing entire window)
- Configurable aggregation functions (mean, median, min, max, last) for downsampling buckets
- No external dependencies added beyond Python standard library

### Test Command

```bash
python tests/run_all.py
```

---

## Task 4: GraphQL Telemetry Query API (API Extension)

### Description

AetherOps currently exposes telemetry data through service-specific REST endpoints scattered across the analytics, reporting, and orbit services. Operations teams have requested a unified query interface that allows flexible telemetry exploration without requiring backend changes for each new dashboard widget or alerting rule.

Implement a GraphQL API layer for telemetry queries that provides a schema covering time-series data, statistical aggregations, and anomaly detection results. The API should support temporal filtering, downsampling at query time, and cross-service correlation (e.g., "show orbit telemetry alongside queue pressure during this burn window").

The implementation must integrate with the existing statistics module for aggregation functions and the telemetry module for anomaly detection. Query complexity limits should prevent expensive queries from impacting system stability. Results should be streamable for large time ranges using GraphQL subscriptions.

### Acceptance Criteria

- GraphQL schema defines Telemetry, StatisticalSummary, Anomaly, and TimeRange types
- Query resolvers integrate with statistics.percentile, statistics.variance, telemetry.detect_drift
- Temporal filtering supports ISO 8601 datetime ranges with timezone awareness
- Query-time downsampling leverages existing telemetry.downsample with configurable factors
- Cross-service correlation joins telemetry streams by timestamp within configurable tolerance
- Query complexity scoring rejects queries exceeding configurable cost threshold
- Subscription support for streaming results with configurable batch sizes
- Authentication middleware validates JWT tokens from identity service

### Test Command

```bash
python tests/run_all.py
```

---

## Task 5: Event Sourcing Migration for Workflow State (Migration)

### Description

The workflow engine currently stores state directly in the WorkflowEngine class instance, which is lost on service restart and cannot be shared across multiple service replicas. This has caused production incidents where workflow state diverged between replicas, leading to duplicate step executions and orphaned workflows.

Migrate the workflow state management to an event sourcing architecture. All state changes should be persisted as immutable events that can be replayed to reconstruct current state. The event store should support temporal queries ("what was the workflow state at timestamp X?") for debugging and audit purposes.

The migration must maintain backward compatibility during the transition period. Existing workflows should continue executing without interruption, with their current state captured as a "snapshot" event. New workflows should be fully event-sourced from creation. The replay mechanism should integrate with the existing resilience module's replay_converges() validation to ensure deterministic state reconstruction.

### Acceptance Criteria

- WorkflowEvent base class with subtypes: WorkflowCreated, StepStarted, StepCompleted, StepFailed, WorkflowCompleted
- EventStore interface with append(event), get_events(workflow_id), get_events_since(timestamp) methods
- WorkflowProjection rebuilds current state from event sequence
- Snapshot events capture existing workflow state at migration time
- Temporal queries return projected state at any historical timestamp
- Replay validation uses resilience.replay_converges() for consistency checks
- Event versioning supports schema evolution with upcasters
- Integration tests verify state consistency across service restarts

### Test Command

```bash
python tests/run_all.py
```
