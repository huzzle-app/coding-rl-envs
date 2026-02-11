# IronFleet - Alternative Tasks

This document describes alternative development tasks for the IronFleet fleet management platform. Each task is independent and focuses on a specific aspect of the convoy mission planning, routing, resilience, and security systems.

---

## Task 1: Real-Time Convoy Position Tracking (Feature Development)

### Description

IronFleet currently handles convoy mission planning and dispatch, but lacks real-time position tracking capabilities. Operations teams need to monitor convoy positions during active missions to detect route deviations, estimate updated arrival times, and respond to emerging threats in contested network environments.

The feature should integrate with the existing routing and analytics modules to provide position updates that feed into health metrics and anomaly detection. Position data must be stored with appropriate checkpoint semantics to support replay and recovery after network partitions. The tracking system should respect the current policy engine state, reducing update frequency during restricted or halted modes.

This feature is critical for situational awareness in autonomous convoy operations where network connectivity may be intermittent and missions span multiple routing channels.

### Acceptance Criteria

- Implement a `PositionTracker` type in the appropriate internal package that stores convoy positions with timestamps
- Position updates must include convoy ID, latitude/longitude coordinates, heading, speed, and channel identifier
- Integrate with `CheckpointManager` to persist position history for replay recovery
- Position queries must be thread-safe and support concurrent read/write access
- Implement deviation detection that compares current position against planned route waypoints
- Position update frequency must respect policy engine state (normal: 30s, watch: 15s, restricted: 60s, halted: disabled)
- Add estimated time of arrival (ETA) recalculation based on current position and remaining route legs
- All existing tests must continue to pass

### Test Command

```bash
go test -race -v ./...
```

---

## Task 2: Consolidate Route Selection Logic (Refactoring)

### Description

The route selection logic is currently scattered across multiple packages: `internal/routing` handles core route selection and channel scoring, `services/routing` provides service-level optimal path computation, and `services/gateway` implements node scoring and route chain building. This distribution creates maintenance burden and risks inconsistent behavior when route selection criteria need to be updated.

The refactoring should consolidate route selection into a unified abstraction while preserving the existing API contracts. The routing package should expose a single entry point for route selection that internally orchestrates channel scoring, node health checks, and multi-leg planning. Gateway-specific concerns like admission control and node selection should delegate to this unified routing layer.

Special attention is needed for the interaction between channel scoring and route selection sorting, as these currently work together to determine optimal routes. The refactoring must maintain deterministic route selection behavior for identical inputs.

### Acceptance Criteria

- Create a `RouteSelector` interface that encapsulates the complete route selection workflow
- Consolidate scoring logic so channel scores and node scores use consistent computation
- Remove duplicate sorting implementations across packages while maintaining API compatibility
- Route selection must remain deterministic given identical inputs and blocked channel sets
- Preserve thread-safety guarantees for concurrent route table access
- Gateway node selection must delegate to the unified routing layer rather than implementing its own scoring
- Document the consolidated routing flow with comments explaining the selection algorithm
- All existing tests must continue to pass without modification

### Test Command

```bash
go test -race -v ./...
```

---

## Task 3: Optimize Queue Shedding Performance (Performance Optimization)

### Description

The current queue management implementation in `internal/queue` performs linear scans and individual item processing during load shedding decisions. Under high load with thousands of queued dispatch orders, the shedding logic becomes a bottleneck. Profiling shows that priority queue operations and shedding decisions account for significant CPU time during burst traffic.

The optimization should improve the algorithmic efficiency of queue operations while maintaining the existing shedding semantics. This includes the `ShouldShed` decision logic, priority queue bulk operations, and rate limiter token management. The queue health metrics computation should also be optimized to avoid recalculating ratios on every status check.

Memory allocation patterns during queue drain operations should be reviewed, as the current implementation creates new slices on each drain call. The goal is to reduce latency and memory pressure during high-throughput dispatch scenarios without changing the queue's observable behavior.

### Acceptance Criteria

- Reduce time complexity of bulk drain operations from O(n) slice copies to amortized O(1)
- Implement lazy health status computation with caching that invalidates on queue state changes
- Rate limiter refill should avoid floating-point drift accumulation over long periods
- Queue operations must remain thread-safe under concurrent access
- Memory allocations during steady-state operations should be minimized
- Shedding decision latency must not increase with queue depth
- Add benchmarks demonstrating improvement (target: 3x throughput for 10,000-item queues)
- All existing tests must continue to pass

### Test Command

```bash
go test -race -v ./...
```

---

## Task 4: External Telemetry Integration API (API Extension)

### Description

Fleet operators need to integrate IronFleet with external monitoring systems like Prometheus, Datadog, and custom SIEM solutions. Currently, the analytics service computes fleet health, trend analysis, and anomaly detection, but these metrics are only available internally. An external-facing telemetry API is required to expose these metrics in a standardized format.

The API should provide structured telemetry data including fleet health ratios, vessel load distributions, queue depths, circuit breaker states, and policy engine transitions. Telemetry queries should support filtering by time range, vessel ID, and metric type. The API must respect security controls and require valid authentication tokens.

Integration with the existing resilience layer is important: telemetry requests should go through circuit breaker protection, and telemetry history should support replay from checkpoints after recovery. High-cardinality metrics like per-convoy position data should be aggregated to prevent metric explosion.

### Acceptance Criteria

- Define a `TelemetryProvider` interface with methods for querying metrics by type and time range
- Implement metric exporters for: fleet health, queue depth, circuit breaker state, policy engine state, routing latency percentiles
- All telemetry queries must validate authentication tokens via the security token store
- Support metric aggregation with configurable granularity (1m, 5m, 15m, 1h buckets)
- Circuit breaker protection for telemetry endpoints to prevent cascading failures
- Telemetry history must integrate with checkpoint manager for replay recovery
- Provide JSON serialization for all metric types suitable for external consumption
- All existing tests must continue to pass

### Test Command

```bash
go test -race -v ./...
```

---

## Task 5: Event Sourcing Migration for Dispatch Orders (Migration)

### Description

The current dispatch order allocation uses mutable state with in-place updates. For audit compliance and disaster recovery requirements, the system needs to migrate to an event-sourced model where all dispatch state changes are captured as immutable events. This enables complete audit trails, point-in-time recovery, and replay of dispatch decisions.

The migration should introduce event types for order submission, allocation, rejection, and completion. The existing `AllocationResult` should be reconstructed from event streams rather than computed directly. This aligns with the resilience package's existing event replay capabilities, enabling unified recovery procedures.

Backward compatibility is critical during the migration period. The system must support reading legacy allocation results while new operations produce event streams. The existing dispatch batch operations must continue to function identically from the caller's perspective.

### Acceptance Criteria

- Define event types: `OrderSubmitted`, `OrderAllocated`, `OrderRejected`, `OrderCompleted` with appropriate fields
- Implement event store with append-only semantics and sequence numbering
- `AllocationResult` must be derivable from replaying the event stream
- Event streams must integrate with the existing `CheckpointManager` for recovery
- Maintain backward compatibility: existing dispatch APIs produce identical results
- Event deduplication must handle replay scenarios correctly
- Implement projection functions to compute current dispatch state from events
- Add migration utility to convert existing allocation results to event streams
- All existing tests must continue to pass

### Test Command

```bash
go test -race -v ./...
```
