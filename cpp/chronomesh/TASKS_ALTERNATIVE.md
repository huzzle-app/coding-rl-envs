# ChronoMesh - Alternative Tasks

These alternative tasks provide different entry points into the ChronoMesh codebase, each focusing on distinct aspects of the time-series maritime dispatch platform.

---

## Task 1: Time-Series Aggregation Pipeline (Feature Development)

### Description

ChronoMesh requires a new time-series aggregation pipeline to support real-time analytics dashboards. Currently, the platform tracks individual dispatch events, response times, and queue metrics, but lacks the ability to aggregate these metrics over configurable time windows (1-minute, 5-minute, 1-hour buckets).

The aggregation pipeline must support multiple aggregation functions (sum, count, average, min, max, percentiles) across sliding and tumbling windows. It should integrate with the existing `ResponseTimeTracker` and queue health monitoring systems to provide rollup statistics that operations teams can use for capacity planning and SLA reporting.

The implementation must be thread-safe and memory-efficient, avoiding unbounded growth of historical data while maintaining accuracy for recent windows. Consider how the aggregation interacts with the checkpoint system for durability guarantees.

### Acceptance Criteria

- Implement a `TimeSeriesAggregator` class that supports configurable window sizes (1m, 5m, 15m, 1h)
- Support both sliding and tumbling window semantics with proper boundary handling
- Implement sum, count, average, min, max, and p95/p99 percentile aggregations
- Aggregate data must be queryable by time range with millisecond precision
- Memory usage must be bounded by configurable maximum retention period
- Thread-safe operations for concurrent writes and reads
- Integration with existing `ResponseTimeTracker` for latency aggregations
- All existing tests continue to pass

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 2: Queue Subsystem Decoupling (Refactoring)

### Description

The queue management subsystem currently has tight coupling between the `PriorityQueue`, `RateLimiter`, and shedding logic. The `should_shed()` function directly references queue depth and hard limits, while rate limiting decisions are made independently without considering queue pressure. This makes it difficult to implement alternative shedding strategies or swap rate limiting algorithms.

Refactor the queue subsystem to introduce a clean separation between queue storage, admission control, and pressure management. The goal is to enable pluggable shedding strategies (priority-based, age-based, random) and rate limiting algorithms (token bucket, leaky bucket, sliding window) without modifying the core queue implementation.

The refactoring must preserve all existing behavior while making the system more testable and extensible. Consider how the `HealthStatus` metrics should be computed when multiple admission control layers are in play.

### Acceptance Criteria

- Extract admission control logic into a separate interface/abstraction
- Implement at least two shedding strategies behind the new interface
- Decouple rate limiting from queue operations while maintaining coordination
- Preserve the existing `HealthStatus` reporting with accurate metrics
- Queue operations remain thread-safe with no additional lock contention
- No changes to the public API signatures of existing functions
- All existing queue-related tests pass without modification
- Add documentation comments explaining the new extension points

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 3: Route Selection Hot Path Optimization (Performance Optimization)

### Description

Profiling has identified the route selection logic as a performance bottleneck during high-throughput dispatch scenarios. The `choose_route()` function is called thousands of times per second, and each call performs a full sort of candidate routes and set lookups for blocked channels. The `RouteTable` class also exhibits contention under concurrent reads and writes.

Optimize the route selection hot path to reduce CPU usage by at least 40% while maintaining correctness. Consider pre-sorting routes, caching blocked channel lookups, using more efficient data structures for the blocked set, and reducing lock contention in the `RouteTable`. The `channel_score()` computation is also called frequently and may benefit from optimization.

The optimization must not change observable behavior or route selection outcomes. Pay particular attention to memory allocation patterns and cache locality in the critical path.

### Acceptance Criteria

- Reduce route selection CPU time by at least 40% (measured via benchmarks)
- Eliminate redundant sorting operations in `choose_route()` hot path
- Optimize blocked channel lookups to O(1) average case
- Reduce lock contention in `RouteTable` for read-heavy workloads
- Minimize heap allocations in the critical path
- Route selection outcomes must be identical to current implementation
- No degradation in multi-leg route planning performance
- All existing routing tests pass without modification

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 4: Batch Dispatch API Extension (API Extension)

### Description

External integrators have requested an enhanced batch dispatch API that supports atomic multi-vessel dispatch operations with rollback capabilities. Currently, `dispatch_batch()` processes orders individually and provides no transactional guarantees. If a berth conflict occurs mid-batch, earlier allocations remain committed while later ones fail.

Extend the dispatch API to support transactional batch operations with all-or-nothing semantics. The API should validate all berth slots, capacity constraints, and order requirements before committing any allocations. If any order in the batch cannot be satisfied, the entire batch should be rejected with detailed error information.

The extension should also support partial batch modes where the caller can specify minimum success thresholds (e.g., "allocate at least 80% of orders or fail"). Consider how this interacts with the existing rolling window scheduler and cost allocation logic.

### Acceptance Criteria

- Implement `dispatch_batch_atomic()` with transactional semantics
- Support configurable minimum success threshold (0-100%)
- Return detailed per-order success/failure reasons in batch results
- Validate all constraints before committing any allocations
- Integrate with existing berth conflict detection and capacity checking
- Cost allocations must be consistent across successful orders in a batch
- Maintain backward compatibility with existing `dispatch_batch()` API
- All existing allocator tests pass without modification

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 5: Checkpoint System Migration to Write-Ahead Log (Migration)

### Description

The current `CheckpointManager` uses an in-memory map with periodic persistence, which can lead to data loss during unexpected shutdowns. The platform needs to migrate to a write-ahead log (WAL) architecture that provides durability guarantees for checkpoint data without sacrificing performance.

Implement a WAL-based checkpoint system that writes all checkpoint updates to an append-only log before acknowledging them. The system should support configurable sync policies (sync-per-write, sync-per-batch, async) to balance durability against throughput. On recovery, the system must replay the WAL to reconstruct checkpoint state.

The migration must be performed incrementally, supporting a hybrid mode where both old and new checkpoint mechanisms operate in parallel during the transition. Consider compaction strategies for the WAL to prevent unbounded growth and ensure fast recovery times.

### Acceptance Criteria

- Implement `WriteAheadLog` class with append, sync, and replay operations
- Support three sync policies: immediate, batched, and async
- WAL compaction to merge old entries and bound log size
- Recovery replay must restore checkpoint state correctly
- Hybrid mode supporting both legacy and WAL checkpoints simultaneously
- Migration utility to convert existing checkpoint data to WAL format
- No data loss guarantee for acknowledged checkpoints under crash scenarios
- Performance regression less than 10% for checkpoint operations
- All existing resilience tests pass without modification

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```
