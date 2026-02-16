# NimbusFlow - Alternative Tasks

This document provides alternative task specifications for the NimbusFlow cloud workflow platform. Each task represents a realistic development scenario that exercises the codebase's core capabilities around resource allocation, workflow orchestration, queue management, and routing.

---

## Task 1: Feature Development - Workflow Checkpoint Recovery

### Description

The NimbusFlow platform currently supports basic checkpoint management through the `CheckpointManager` class, but lacks a comprehensive recovery mechanism for workflows that fail mid-execution. Operations teams have requested the ability to resume workflows from their last successful checkpoint rather than restarting from the beginning.

Implement a workflow checkpoint recovery system that integrates with the existing `WorkflowEngine` and `CheckpointManager`. The recovery system should detect incomplete workflows (those not in a terminal state), locate their most recent checkpoint, and provide a recovery path that respects the workflow state machine transitions. Recovery should support both automatic and manual recovery modes, with automatic recovery kicking in after a configurable timeout.

The feature should integrate with the existing `Resilience` module's circuit breaker pattern to prevent recovery storms during system-wide failures. Recovery attempts should respect policy escalation states - workflows should not recover automatically when the system is in "halted" or "restricted" policy modes.

### Acceptance Criteria

- Recovery detects workflows in non-terminal states that have been inactive beyond a configurable threshold
- Recovery respects the workflow state machine - only valid transitions are allowed during recovery
- Checkpoints are validated against sequence numbers to ensure recovery uses the most recent valid checkpoint
- Circuit breaker integration prevents cascading recovery attempts during system failures
- Policy mode restrictions prevent automatic recovery during "halted" or "restricted" states
- Recovery events are recorded in the workflow audit log with appropriate timestamps
- Concurrent recovery attempts on the same workflow are prevented through proper locking
- Recovery statistics (attempts, successes, failures) are tracked in the Statistics module

### Test Command

```bash
mvn test
```

---

## Task 2: Refactoring - Unified Rate Limiting Strategy

### Description

The NimbusFlow codebase currently implements rate limiting through the `RateLimiter` class using a token bucket algorithm, while the `QueueGuard` module handles load shedding with separate thresholds. This dual approach has led to inconsistent behavior where requests might pass rate limiting but get shed at the queue, or vice versa, causing confusion in incident response.

Refactor the rate limiting infrastructure to provide a unified rate limiting strategy that coordinates between token bucket admission and queue depth shedding. The refactored solution should provide a single decision point for request admission that considers both token availability and queue health status.

The refactoring should maintain backward compatibility with existing callers of both `RateLimiter` and `QueueGuard`, but internally route through the unified strategy. This allows gradual migration of callers to the new unified API while ensuring consistent behavior immediately. The unified strategy should also integrate with the `QueueHealthMonitor` to provide real-time visibility into admission decisions.

### Acceptance Criteria

- Unified admission decision combines token bucket availability with queue depth thresholds
- Existing `RateLimiter.tryAcquire()` API remains functional with unchanged behavior for gradual migration
- Existing `QueueGuard.shouldShed()` API remains functional with unchanged behavior
- New unified API provides single admission check with detailed rejection reasons
- Queue health status is considered in admission decisions (emergency mode triggers earlier shedding)
- Admission decisions are logged with enough detail for post-incident analysis
- Thread-safe implementation maintains correct behavior under concurrent access
- Response time impact is minimal - admission decisions complete within microseconds

### Test Command

```bash
mvn test
```

---

## Task 3: Performance Optimization - Route Selection Caching

### Description

Performance profiling of the NimbusFlow routing layer has revealed that `Routing.chooseRoute()` and `Routing.channelScore()` are called repeatedly with identical parameters during multi-leg route planning. Each call performs filtering, sorting, and score calculations that are computationally expensive when route tables contain hundreds of channels.

Optimize route selection performance by implementing an intelligent caching layer that memoizes route selection results and channel scores. The cache should be invalidated when routes are added or removed from the `RouteTable`, when channel blocking status changes, or when scoring parameters (reliability, priority) are updated.

The caching strategy should balance memory usage against hit rates. Routes that change frequently (high-traffic channels) should use shorter cache TTLs, while stable routes can use longer TTLs. The optimization should integrate with the `Statistics` module to track cache hit rates and identify opportunities for further optimization.

### Acceptance Criteria

- Route selection results are cached with configurable TTL based on route stability
- Channel score calculations are memoized with proper invalidation on parameter changes
- Cache invalidation triggers correctly when RouteTable is modified (add/remove routes)
- Blocking status changes invalidate affected route cache entries only
- Memory usage is bounded with LRU eviction when cache size exceeds limits
- Cache statistics (hits, misses, evictions) are exposed through Statistics module
- Multi-leg planning benefits from cached single-leg results
- Concurrent access to cache maintains consistency without excessive locking

### Test Command

```bash
mvn test
```

---

## Task 4: API Extension - Dispatch Order Priority Override

### Description

Maritime operations often require the ability to expedite specific dispatch orders in response to real-time events such as weather changes, port congestion, or customer escalations. Currently, the `Allocator.planDispatch()` function sorts orders strictly by urgency and SLA, with no mechanism to override priorities for specific orders.

Extend the dispatch allocation API to support priority overrides that can elevate or suppress specific orders relative to their calculated priority. Overrides should be time-bounded (automatic expiration) and require authorization tracking for audit purposes. The system should prevent override abuse by limiting the number of active overrides and requiring minimum intervals between override changes for the same order.

The extension should integrate with the `Policy` module - priority overrides may be restricted or disabled entirely when the system is in "watch" or higher escalation states. Override history should be maintained for compliance reporting, with the ability to query which orders had overrides active during a given time window.

### Acceptance Criteria

- Priority overrides can elevate or suppress order priority relative to calculated `urgencyScore()`
- Overrides have mandatory expiration times and automatically revert to normal priority
- Authorization tracking records who created each override and when
- Active override count limits prevent system-wide priority manipulation
- Minimum interval between override changes prevents rapid priority toggling
- Policy state restrictions limit override creation during elevated policy modes
- Override history is queryable by time range and order ID for compliance audits
- `planDispatch()` correctly orders items considering active overrides while maintaining stability

### Test Command

```bash
mvn test
```

---

## Task 5: Migration - Event Replay to Event Sourcing

### Description

The current `Resilience.replay()` function provides basic event deduplication and ordering but lacks the full event sourcing capabilities needed for complex audit requirements. Compliance teams need the ability to reconstruct the exact state of any workflow at any point in time, which requires maintaining the complete event history rather than just the latest state.

Migrate the event replay infrastructure to a full event sourcing pattern where all state changes are derived from an append-only event log. The migration should be backward-compatible, supporting both the existing replay behavior and the new event sourcing queries. The event store should support snapshotting to prevent unbounded event log growth while maintaining point-in-time reconstruction capabilities.

The migration should integrate with the `CheckpointManager` to leverage existing checkpoint infrastructure for snapshot storage. Event sourced state reconstruction should work with the `WorkflowEngine` to rebuild workflow state from events, and with the `PolicyEngine` to reconstruct policy state history for incident analysis.

### Acceptance Criteria

- Append-only event log captures all state changes with immutable event records
- Point-in-time state reconstruction returns exact state at any historical timestamp
- Snapshot creation reduces event replay overhead for frequently-accessed entities
- Backward-compatible `replay()` function continues to work with existing callers
- Event projection supports rebuilding `WorkflowEngine` state from event history
- Event projection supports rebuilding `PolicyEngine` state from event history
- Event log compaction with snapshot retention maintains bounded storage growth
- Concurrent event appends and queries maintain consistency under load

### Test Command

```bash
mvn test
```
