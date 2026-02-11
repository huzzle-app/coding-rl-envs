# ObsidianMesh - Alternative Tasks

## Overview

ObsidianMesh supports five alternative engineering tasks that focus on feature development, system refactoring, performance optimization, API extension, and infrastructure migration—all using the same codebase but testing different software engineering skills than the core debugging environment.

## Environment

- **Language**: C++ (C++20)
- **Infrastructure**: Docker-based with CMake build system, 14 source modules, 13 microservices
- **Difficulty**: Apex-Principal
- **Test Framework**: ctest with ~12,678 test cases

## Tasks

### Task 1: Multi-Zone Mesh Partitioning (Feature Development)

Implement a multi-zone partitioning system that allows nodes to be assigned to geographic zones with intelligent cross-zone routing policies. The system should prefer intra-zone routing when possible while maintaining cross-zone connectivity for resilience. Zone affinity should be configurable with latency-based fallback thresholds that trigger cross-zone routing when local zone health degrades.

The partitioning system must integrate with the existing circuit breaker and routing infrastructure. When a zone experiences degraded health, traffic should automatically spill over to healthy zones while respecting capacity constraints. Zone health should be derived from aggregate node health metrics using the existing telemetry infrastructure.

### Task 2: Unified Queue Management Refactoring (Refactoring)

Refactor the queue management subsystem into a cohesive `MeshQueue` abstraction that unifies priority ordering, rate limiting, admission control, and health monitoring into a single consistent interface. The refactored design should maintain backward compatibility with existing function signatures while providing a cleaner internal implementation.

The current queue management implementation is fragmented across multiple components, leading to inconsistent behavior when components interact. Address coupling issues where admission control ignores queue depth, pressure calculations ignore processing rates, and health metrics are computed independently of rate limiter state.

### Task 3: Hot Path Latency Optimization (Performance Optimization)

Optimize the mesh routing hot path to minimize latency under high request volumes. Profiling has revealed that the `choose_route` function performs a full sort on every call, `channel_score` recalculates derived metrics repeatedly, and route selection involves multiple allocations per request. The routing table should maintain pre-sorted candidate lists that are updated incrementally when routes change. Frequently accessed route scores should be cached and invalidated only when underlying metrics change.

The optimization must preserve correctness of route selection and maintain thread-safety guarantees. Optimized paths should produce identical results to the current implementation and target the common case where routes change infrequently relative to route lookups.

### Task 4: Event Streaming API Extension (API Extension)

Extend the event subsystem with a streaming API that supports long-lived event subscriptions with continuous event consumption, backpressure handling, cursor-based pagination for historical replay, and subscription filters for selective event routing. Subscribers should receive events in real-time with configurable buffering and backpressure signaling.

The streaming API must integrate with the existing checkpoint manager for durable cursor positions. Subscribers that disconnect and reconnect should resume from their last acknowledged position. The API should support both push-based delivery (for real-time subscribers) and pull-based consumption (for batch processors).

### Task 5: Statistics Engine to Time-Series Backend Migration (Migration)

Migrate the statistics subsystem from in-memory vectors to a time-series storage abstraction. The new architecture should define a `TimeSeriesStore` interface that can be backed by different storage implementations (in-memory for testing, file-based for single-node deployments, or external database for production). The migration should preserve all existing statistical calculations while enabling new capabilities like historical range queries and retention-based eviction.

The migration must be non-breaking for existing code. Current function signatures should continue to work by defaulting to an in-memory time-series store. The `ResponseTimeTracker` class should be refactored to use the new storage abstraction while maintaining its current API.

## Getting Started

```bash
cmake -B build && cmake --build build
ctest --test-dir build --output-on-failure
```

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md), including:

- For Task 1: Multi-zone partitioning, zone health aggregation, cross-zone routing, automatic traffic redistribution
- For Task 2: Unified `MeshQueue` abstraction, backward compatibility, consistent state management, coherent metrics
- For Task 3: Pre-sorted routing tables, cached scores, eliminated allocations, identical correctness, thread-safety preservation
- For Task 4: Streaming subscriptions, backpressure, cursor-based pagination, filters, checkpoint integration
- For Task 5: `TimeSeriesStore` interface, multiple implementations, backward compatibility, range queries, retention policies

All changes must compile cleanly without warnings and pass the full test suite.
