# ObsidianMesh - Alternative Tasks

These alternative tasks represent realistic engineering work on the ObsidianMesh distributed mesh platform. Each task focuses on a specific aspect of the system without revealing implementation details.

---

## Task 1: Multi-Zone Mesh Partitioning (Feature Development)

ObsidianMesh currently routes traffic through a single logical mesh without geographic awareness. As the platform scales to support global deployments, operators need the ability to partition the mesh into geographic zones with intelligent cross-zone routing policies.

Implement a multi-zone partitioning system that allows nodes to be assigned to geographic zones (e.g., "us-east", "eu-west", "ap-south"). The system should prefer intra-zone routing when possible while maintaining cross-zone connectivity for resilience. Zone affinity should be configurable with latency-based fallback thresholds that trigger cross-zone routing when local zone health degrades.

The partitioning system must integrate with the existing circuit breaker and routing infrastructure. When a zone experiences degraded health, traffic should automatically spill over to healthy zones while respecting capacity constraints. Zone health should be derived from aggregate node health metrics using the existing telemetry infrastructure.

### Acceptance Criteria

- Nodes can be assigned to named geographic zones with configurable affinity weights
- Intra-zone routing is preferred with configurable latency threshold for cross-zone fallback
- Zone health is computed from aggregate node metrics (error rate, latency percentiles)
- Cross-zone traffic respects destination zone capacity limits
- Zone partitioning integrates with existing circuit breaker state transitions
- Failing zones trigger automatic traffic redistribution to healthy zones
- Zone topology changes propagate within configurable convergence windows
- All zone routing decisions are logged for audit compliance

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 2: Unified Queue Management Refactoring (Refactoring)

The current queue management implementation is fragmented across multiple components. The `PriorityQueue` class handles item ordering, `RateLimiter` manages throughput, `batch_enqueue_count` handles admission control, and `queue_health` computes metrics. This separation leads to inconsistent behavior when these components interact and makes it difficult to reason about end-to-end queue behavior.

Refactor the queue management subsystem into a cohesive `MeshQueue` abstraction that unifies priority ordering, rate limiting, admission control, and health monitoring into a single consistent interface. The refactored design should maintain backward compatibility with existing function signatures while providing a cleaner internal implementation.

The refactoring should address the current coupling issues where admission control ignores queue depth, pressure calculations ignore processing rates, and health metrics are computed independently of rate limiter state. The unified abstraction should ensure these components share consistent state and produce coherent metrics.

### Acceptance Criteria

- New `MeshQueue` class unifies priority queue, rate limiting, and admission control
- Existing public function signatures remain backward compatible
- Admission control considers both queue depth and rate limiter state
- Pressure ratio incorporates incoming and processing rates
- Health metrics reflect unified queue state including rate limiter tokens
- Fair queuing across services is enforced at the unified abstraction level
- Drain operations respect rate limits and priority ordering simultaneously
- Queue pressure triggers coordinated backpressure across all queue dimensions

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 3: Hot Path Latency Optimization (Performance Optimization)

Profiling has revealed that the mesh routing hot path incurs significant overhead during high-throughput scenarios. The `choose_route` function performs a full sort on every call, `channel_score` recalculates derived metrics repeatedly, and route selection involves multiple allocations per request.

Optimize the routing hot path to minimize latency under high request volumes. The routing table should maintain pre-sorted candidate lists that are updated incrementally when routes change. Frequently accessed route scores should be cached and invalidated only when underlying metrics change. Memory allocations on the hot path should be eliminated through object pooling or pre-allocation.

The optimization must preserve correctness of route selection and maintain thread-safety guarantees. Optimized paths should produce identical results to the current implementation. The optimization should target the common case where routes change infrequently relative to route lookups.

### Acceptance Criteria

- Route selection eliminates per-request sorting through pre-maintained sorted lists
- Channel scores are cached with invalidation on underlying metric changes
- Hot path allocations are eliminated through pooling or pre-allocation
- Route table updates incrementally maintain sorted candidate order
- Thread-safety is preserved with minimal lock contention on read-heavy workloads
- Optimized code produces identical results to current implementation
- Cache hit rates are tracked through telemetry for monitoring
- Memory usage remains bounded under sustained high-throughput scenarios

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 4: Event Streaming API Extension (API Extension)

The current event infrastructure provides basic replay, deduplication, and windowing capabilities through standalone functions. Operators have requested a streaming API that supports continuous event consumption with backpressure, cursor-based pagination for historical replay, and subscription filters for selective event routing.

Extend the event subsystem with a streaming API that supports long-lived event subscriptions. Subscribers should receive events in real-time with configurable buffering and backpressure signaling. Historical replay should support cursor-based pagination that resumes from any sequence position. Event filters should allow subscribers to receive only events matching specified criteria (by ID prefix, sequence range, or custom predicates).

The streaming API must integrate with the existing checkpoint manager for durable cursor positions. Subscribers that disconnect and reconnect should resume from their last acknowledged position. The API should support both push-based delivery (for real-time subscribers) and pull-based consumption (for batch processors).

### Acceptance Criteria

- New `EventSubscription` class supports long-lived streaming subscriptions
- Backpressure signaling pauses event delivery when subscriber buffers fill
- Cursor-based pagination enables resumable historical replay from any sequence
- Event filters support ID prefix matching, sequence ranges, and custom predicates
- Checkpoint integration persists subscriber cursor positions durably
- Reconnecting subscribers resume from last acknowledged sequence
- Push-based delivery mode for real-time consumers with configurable buffer size
- Pull-based consumption mode for batch processors with page size control

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 5: Statistics Engine to Time-Series Backend Migration (Migration)

The current statistics implementation stores samples in memory-only vectors with bounded windows. Operations teams require migration to a time-series backend model that supports persistent storage, configurable retention policies, and efficient range queries over historical data.

Migrate the statistics subsystem from in-memory vectors to a time-series storage abstraction. The new architecture should define a `TimeSeriesStore` interface that can be backed by different storage implementations (in-memory for testing, file-based for single-node deployments, or external database for production). The migration should preserve all existing statistical calculations while enabling new capabilities like historical range queries and retention-based eviction.

The migration must be non-breaking for existing code. Current function signatures should continue to work by defaulting to an in-memory time-series store. The `ResponseTimeTracker` class should be refactored to use the new storage abstraction while maintaining its current API. Statistical aggregations (mean, variance, percentiles) should work efficiently over the time-series storage.

### Acceptance Criteria

- New `TimeSeriesStore` interface abstracts underlying storage implementation
- In-memory implementation preserves current behavior for backward compatibility
- File-based implementation supports single-node persistent deployments
- Configurable retention policies evict data older than specified durations
- Range queries retrieve samples within specified time windows efficiently
- `ResponseTimeTracker` migrated to use time-series storage internally
- Statistical aggregations (mean, percentile, EMA) work over stored time-series
- Existing public function signatures continue to work unchanged

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```
