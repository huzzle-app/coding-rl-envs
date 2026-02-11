# ChronoMesh - Alternative Tasks

## Overview

These five alternative tasks provide different entry points into the ChronoMesh codebase, each focusing on extending or optimizing distinct aspects of the maritime dispatch platform. Choose any task to test feature development, refactoring, performance optimization, API extension, and infrastructure migration skills.

## Environment

- **Language**: C++20
- **Infrastructure**: Docker-based testing with CMake build system
- **Difficulty**: Hyper-Principal (70-140 hours)

## Tasks

### Task 1: Time-Series Aggregation Pipeline (Feature Development)

Implement a new time-series aggregation pipeline to support real-time analytics dashboards. The platform currently tracks individual dispatch events and response times but lacks aggregation over configurable time windows (1-minute, 5-minute, 1-hour buckets). Design and build a `TimeSeriesAggregator` class supporting multiple aggregation functions (sum, count, average, min, max, percentiles) with both sliding and tumbling window semantics. Integrate with the existing `ResponseTimeTracker` and queue monitoring systems while maintaining thread safety and bounded memory usage.

### Task 2: Queue Subsystem Decoupling (Refactoring)

Refactor the queue management subsystem to decouple the tightly-coupled `PriorityQueue`, `RateLimiter`, and shedding logic. Extract admission control into a separate abstraction that enables pluggable shedding strategies (priority-based, age-based, random) and rate limiting algorithms (token bucket, leaky bucket, sliding window) without modifying core queue implementation. Preserve all existing behavior while making the system more testable and extensible, maintaining accurate `HealthStatus` reporting through multiple admission control layers.

### Task 3: Route Selection Hot Path Optimization (Performance Optimization)

Profile and optimize the route selection logic identified as a performance bottleneck during high-throughput dispatch scenarios. The `choose_route()` function is called thousands of times per second and performs expensive sorts and set lookups. Reduce CPU usage by at least 40% through pre-sorting, caching blocked channel lookups, more efficient data structures, and reduced lock contention in `RouteTable`. Maintain identical route selection outcomes while optimizing memory allocation patterns and cache locality in the critical path.

### Task 4: Batch Dispatch API Extension (API Extension)

Extend the dispatch API to support atomic multi-vessel batch operations with rollback capabilities. Currently, `dispatch_batch()` provides no transactional guarantees. Implement `dispatch_batch_atomic()` with all-or-nothing semantics that validates all berth slots, capacity constraints, and order requirements before committing any allocations. Support partial batch modes with configurable minimum success thresholds, detailed error reporting per order, and integration with the existing rolling window scheduler and cost allocation logic.

### Task 5: Checkpoint System Migration to Write-Ahead Log (Migration)

Migrate the `CheckpointManager` from an in-memory map with periodic persistence to a write-ahead log (WAL) architecture for durability guarantees. Implement a `WriteAheadLog` class with configurable sync policies (sync-per-write, sync-per-batch, async) and compaction strategies to prevent unbounded growth. Support hybrid mode where both old and new checkpoint mechanisms operate in parallel during transition, with recovery replay to reconstruct checkpoint state and ensure no data loss for acknowledged checkpoints under crash scenarios.

## Getting Started

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug && cmake --build build && ctest --test-dir build --output-on-failure
```

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) for the chosen task. All existing tests must continue to pass, and new functionality must be thread-safe, well-integrated with the existing codebase, and follow established architectural patterns.
