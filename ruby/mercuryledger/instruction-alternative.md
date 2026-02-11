# MercuryLedger - Alternative Tasks

## Overview

Five alternative engineering tasks that extend and improve the MercuryLedger settlement platform. These tasks test feature development, refactoring, performance optimization, API design, and system migration skills using the existing Ruby codebase.

## Environment

- **Language**: Ruby 3.2
- **Infrastructure**: Docker Compose, Minitest, 8 interconnected services, 9 core modules
- **Difficulty**: Hyper-Principal (70-140 hours estimated for all five tasks)

## Tasks

### Task 1: Multi-Currency Settlement Support (Feature Development)

Extend MercuryLedger's settlement pipeline to support multiple ISO 4217 currencies with automatic exchange rate handling. Orders must specify a currency code, dispatch planning must group settlements by currency, and cost estimation must convert amounts to a base currency (USD) before totaling. Updates to statistics tracking should include currency breakdowns.

**Key Components**: ExchangeRateProvider with staleness detection, currency-aware dispatch_batch grouping, cost conversion functions, thread-safe caching

**Acceptance Criteria**:
- Orders support currency field with ISO 4217 codes
- Dispatch batch groups by currency before capacity limits
- Cost estimation accepts base_currency parameter with conversion
- Statistics reports currency breakdowns
- All existing tests pass with default USD behavior

### Task 2: Circuit Breaker Pattern Consolidation (Refactoring)

Consolidate ad-hoc circuit breaker implementations scattered across services into a unified infrastructure. Create a CircuitBreakerRegistry singleton managing named instances with per-service configuration, add an observer interface for state transitions, and eliminate code duplication while preserving existing behavior.

**Key Components**: CircuitBreakerRegistry singleton, unified configuration structure, CircuitBreakerObserver interface, health_report aggregation

**Acceptance Criteria**:
- Create CircuitBreakerRegistry managing all circuit breakers
- All services use registry instances instead of custom implementations
- Configuration externalized with per-service overrides
- Observer interface for logging/alerting on state changes
- Registry exposes centralized health_report
- All resilience tests pass

### Task 3: Queue Batch Processing Optimization (Performance Optimization)

Replace the current O(n log n) per-insertion priority queue with efficient batch operations. Implement enqueue_batch and dequeue_batch methods that acquire locks once per batch. Use a binary heap for O(log n) insertion and add burst allowances to the rate limiter for temporary spikes.

**Key Components**: Binary heap data structure, batch enqueue/dequeue/peek operations, RateLimiter burst_allowance parameter, performance benchmarks

**Acceptance Criteria**:
- enqueue_batch performs single sort operation
- dequeue_batch retrieves multiple items in one lock
- Binary heap replaces array-based storage
- peek_batch inspects top N items without removal
- RateLimiter supports burst_allowance parameter
- At least 3x throughput improvement for batches of 100+ items
- Memory usage does not exceed 2x current implementation

### Task 4: Corridor Analytics API Extension (API Extension)

Extend the routing module with comprehensive analytical capabilities for route optimization. Add historical corridor performance tracking, comparison API with configurable weighting, predictive transit time estimation with confidence intervals, and anomaly detection using statistical variance.

**Key Components**: CorridorAnalytics class, compare_corridors ranking, predict_transit_time with confidence intervals, heatmap-ready events, anomaly detection

**Acceptance Criteria**:
- CorridorAnalytics tracks metrics over configurable time windows
- compare_corridors returns ranked corridors with weighted criteria
- predict_transit_time includes confidence intervals from historical variance
- Corridor utilization suitable for heatmap generation
- performance_summary returns p50/p95/p99 latencies
- anomaly_detection flags corridors outside 2 standard deviations
- Historical data supports configurable retention with pruning

### Task 5: Token Store to Redis Migration (Migration)

Migrate token storage from in-memory hash to Redis with backward-compatible API. Introduce a TokenStoreAdapter interface with InMemoryTokenStore and RedisTokenStore implementations, add connection pooling, implement retry logic with exponential backoff, and support token sharding across multiple Redis keys using consistent hashing.

**Key Components**: TokenStoreAdapter interface, InMemoryTokenStore and RedisTokenStore implementations, connection pooling, exponential backoff retry, ShardedRedisTokenStore

**Acceptance Criteria**:
- TokenStoreAdapter defines interface (store, valid?, revoke, cleanup, count)
- InMemoryTokenStore is drop-in replacement for current implementation
- RedisTokenStore uses HSET/HGET with TTL via EXPIRE
- Connection pooling with configurable size and timeout
- Exponential backoff for transient failures
- ShardedRedisTokenStore distributes tokens via consistent hashing
- Migration script transfers tokens without downtime
- All security tests pass with both implementations

## Getting Started

```bash
cd ruby/mercuryledger
bundle exec rspec
```

Or using the standard test runner:

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Success Criteria

Implementation of all five tasks meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). Each task preserves existing functionality, maintains the Ruby architectural patterns used throughout the codebase, and includes comprehensive test coverage.
