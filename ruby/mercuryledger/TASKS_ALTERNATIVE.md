# MercuryLedger - Alternative Tasks

These alternative tasks provide different ways to engage with the MercuryLedger codebase beyond debugging. Each task focuses on extending or improving specific aspects of the ledger platform.

---

## Task 1: Multi-Currency Settlement Support (Feature Development)

MercuryLedger currently handles settlement orders with a single implicit currency. As the platform expands to support international maritime operations, we need to add multi-currency settlement capabilities to the dispatch and order processing pipeline.

The feature should allow orders to specify a currency code (ISO 4217) and include exchange rate handling when aggregating costs across different currencies. The dispatch batch planning must be aware of currency boundaries, ensuring that settlements in the same currency are grouped together for efficient processing. Additionally, the cost estimation functions need to convert all amounts to a base currency (USD) before calculating totals.

This change impacts the core order processing, dispatch planning, and cost allocation modules. The statistics tracking should also be updated to report settlement volumes broken down by currency.

### Acceptance Criteria

- Orders can specify a `currency` field with valid ISO 4217 codes (USD, EUR, GBP, JPY, etc.)
- Add an `ExchangeRateProvider` class that maintains current exchange rates with timestamp-based staleness detection
- The `dispatch_batch` function groups orders by currency before applying capacity limits
- Cost estimation functions accept an optional `base_currency` parameter and convert amounts accordingly
- The `allocate_costs` function respects currency boundaries and does not mix allocations across currencies
- Statistics tracking includes currency breakdown in settlement reports
- All existing tests continue to pass with default USD currency behavior
- Thread-safe exchange rate caching with configurable refresh intervals

### Test Command

```bash
bundle exec rspec
```

---

## Task 2: Circuit Breaker Pattern Consolidation (Refactoring)

The resilience module contains a `CircuitBreaker` class, but similar circuit breaker patterns are implemented ad-hoc in various services (gateway scoring, notification throttling, routing failover). This leads to inconsistent failure handling and makes it difficult to monitor system-wide resilience.

Refactor the codebase to consolidate all circuit breaker implementations into a unified, configurable circuit breaker infrastructure. Each service should use the same underlying `CircuitBreaker` class with service-specific configuration for thresholds, timeouts, and recovery behavior. The refactoring should preserve existing behavior while eliminating code duplication.

The consolidated approach should also introduce a `CircuitBreakerRegistry` that tracks all active circuit breakers in the system, enabling centralized health monitoring and coordinated recovery strategies.

### Acceptance Criteria

- Create a `CircuitBreakerRegistry` singleton that manages named circuit breaker instances
- All services use `CircuitBreaker` instances obtained from the registry rather than custom implementations
- Circuit breaker configuration is externalized into a `resilience_config` structure with per-service overrides
- Add a `CircuitBreakerObserver` interface for hooking into state transitions (for logging/alerting)
- The registry exposes a `health_report` method returning the state of all circuit breakers
- Existing half-open probing behavior is preserved during the refactoring
- Remove all duplicate circuit breaker implementations from service modules
- All existing resilience tests continue to pass

### Test Command

```bash
bundle exec rspec
```

---

## Task 3: Queue Batch Processing Optimization (Performance Optimization)

The current `PriorityQueue` implementation processes items one at a time, which creates significant overhead when handling high-volume settlement workloads. Each `dequeue` operation acquires a mutex lock, and the queue is re-sorted on every `enqueue`, leading to O(n log n) complexity per insertion.

Optimize the queue management system to support efficient batch operations. Implement a batch enqueue method that accepts multiple items and performs a single sort operation. Add a batch dequeue method that retrieves up to N items in a single locked operation. Consider using a heap-based data structure instead of sorting the full array on each insertion.

Additionally, the `RateLimiter` should be optimized to support burst allowances, where a configurable number of requests can exceed the normal rate limit before throttling kicks in.

### Acceptance Criteria

- Implement `enqueue_batch(items_with_priorities)` that accepts an array of item/priority pairs and performs one sort
- Implement `dequeue_batch(count)` that retrieves up to `count` items in a single mutex acquisition
- Replace the array-based storage with a binary heap for O(log n) insertion complexity
- Add `peek_batch(count)` to inspect the top N items without removing them
- The `RateLimiter` supports a `burst_allowance` parameter that permits temporary rate spikes
- Benchmark the batch operations to ensure at least 3x throughput improvement for batches of 100+ items
- Memory usage should not exceed 2x the current implementation for equivalent workloads
- All existing queue tests continue to pass

### Test Command

```bash
bundle exec rspec
```

---

## Task 4: Corridor Analytics API Extension (API Extension)

The routing module provides basic corridor selection and transit time estimation, but lacks analytical capabilities that operations teams need for route optimization decisions. Extend the routing API to support historical analysis, corridor comparison, and predictive transit time estimation.

Add methods to track historical corridor performance (latency, reliability, cost) over time windows. Implement a corridor comparison API that ranks multiple routes based on configurable criteria weights. Introduce predictive transit time estimation that factors in historical variance, time-of-day patterns, and current traffic conditions.

The analytics extension should integrate with the existing `Statistics` module for percentile calculations and moving averages, and expose data suitable for the `HeatmapGenerator` to visualize corridor utilization patterns.

### Acceptance Criteria

- Add `CorridorAnalytics` class that tracks per-corridor metrics over configurable time windows
- Implement `compare_corridors(corridor_ids, weights)` that returns ranked corridors based on weighted criteria
- Add `predict_transit_time(corridor_id, departure_time)` that uses historical variance for confidence intervals
- Track corridor utilization as events suitable for heatmap generation (hour-of-day vs day-of-week)
- Expose `performance_summary(corridor_id, time_range)` returning p50/p95/p99 latencies
- Add `anomaly_detection(corridor_id)` that flags corridors performing outside 2 standard deviations
- Historical data supports configurable retention periods with automatic pruning
- All existing routing tests continue to pass

### Test Command

```bash
bundle exec rspec
```

---

## Task 5: Token Store to Redis Migration (Migration)

The `TokenStore` class currently uses an in-memory hash for storing authentication tokens, which does not support horizontal scaling or persistence across process restarts. Migrate the token storage to Redis while maintaining backward compatibility with the existing API.

The migration should introduce a `TokenStoreAdapter` interface that abstracts the storage backend, with both `InMemoryTokenStore` and `RedisTokenStore` implementations. The Redis implementation must handle connection failures gracefully, falling back to deny-by-default behavior rather than crashing. Token serialization should use a compact binary format to minimize Redis memory usage.

Additionally, implement token storage sharding for high-volume deployments, distributing tokens across multiple Redis keys based on a consistent hashing scheme.

### Acceptance Criteria

- Create `TokenStoreAdapter` module defining the interface (store, valid?, revoke, cleanup, count)
- Implement `InMemoryTokenStore` as a drop-in replacement for the current implementation
- Implement `RedisTokenStore` that uses Redis HSET/HGET with TTL support via EXPIRE
- Add connection pooling for Redis with configurable pool size and timeout
- Implement retry logic with exponential backoff for transient Redis failures
- Add `ShardedRedisTokenStore` that distributes tokens across N Redis keys using consistent hashing
- Include a migration script that transfers tokens from in-memory to Redis without downtime
- All existing security tests continue to pass with both adapter implementations

### Test Command

```bash
bundle exec rspec
```
