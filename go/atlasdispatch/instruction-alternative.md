# AtlasDispatch - Alternative Tasks

## Overview

This document describes five realistic development tasks for the AtlasDispatch maritime dispatch and routing platform. These tasks test feature development, refactoring, performance optimization, API design, and system migration skills using the same codebase.

## Environment

- **Language**: Go
- **Infrastructure**: Maritime dispatch system with routing, allocation, rate limiting, event replay, and policy management
- **Difficulty**: Hyper-Principal
- **Test Command**: `go test -v ./...`

## Tasks

### Task 1: Multi-Carrier Route Optimization (Feature Development)

AtlasDispatch currently selects routes based on single-carrier latency metrics. Customers have requested support for multi-carrier routing where cargo can be split across multiple shipping partners to optimize for cost, time, and reliability constraints simultaneously.

Implement a multi-carrier route optimization system that can evaluate composite routes involving handoffs between carriers. The system should consider inter-carrier transfer times, customs clearance delays at handoff points, and aggregate reliability scores across the entire route chain. Routes must be scored using a weighted objective function that balances transit time, total cost, and minimum reliability thresholds.

**Acceptance Criteria:**
- Multi-carrier routes can be constructed from individual carrier segments with handoff waypoints
- Composite route scoring accounts for transfer delays (minimum 4 hours per handoff)
- Reliability scores are calculated as the product of individual carrier reliabilities
- Cost estimation includes per-handoff surcharges and carrier-specific fuel rates
- Routes violating carrier partnership constraints are automatically excluded
- System falls back to single-carrier routing when no valid multi-carrier option exists
- All route selections are logged with scoring breakdown for audit purposes

### Task 2: Queue Management Refactoring (Refactoring)

The current queue management implementation exhibits architectural issues. The PriorityQueue directly couples sorting logic with enqueueing, the RateLimiter mixes time management with token accounting, and load shedding decisions are scattered across multiple functions.

Refactor the queue management system to follow a cleaner separation of concerns. Extract a dedicated QueuePolicy interface that encapsulates priority ordering, admission control, and shedding strategies. This will enable future support for different queue disciplines (FIFO, weighted fair queuing, deadline-based) without modifying the core queue implementation.

**Acceptance Criteria:**
- QueuePolicy interface defines methods for priority comparison, admission decisions, and shed targeting
- PriorityQueue accepts a QueuePolicy implementation at construction time
- Default policy preserves current behavior (priority-based ordering with depth-based shedding)
- RateLimiter token management is separated from time source for testing
- Load shedding logic is consolidated into a single, configurable ShedStrategy
- All existing queue operations maintain their concurrency guarantees
- No changes to external API signatures for backward compatibility

### Task 3: Checkpoint and Replay Performance Optimization (Performance Optimization)

Production telemetry indicates that the event replay and checkpoint system becomes a bottleneck during high-throughput recovery scenarios. When replaying large event streams (50,000+ events), the current implementation shows O(n²) behavior due to repeated map lookups and slice reallocations during deduplication.

Optimize the replay pipeline to achieve linear time complexity for event deduplication and ordering. The checkpoint manager should support batch operations to reduce lock contention during high-frequency checkpointing. Consider implementing a tiered checkpoint strategy where recent events use in-memory checkpoints while older segments are persisted.

**Acceptance Criteria:**
- Event replay achieves O(n log n) time complexity for streams up to 100,000 events
- Checkpoint batch operations reduce lock acquisitions by at least 80% for burst writes
- Memory allocation during replay is reduced by pre-sizing data structures
- Deduplication uses efficient key encoding that avoids string concatenation overhead
- Tiered checkpointing supports configurable thresholds for memory vs persistence boundaries
- Replay determinism is verified through convergence testing with randomized input orders
- Performance benchmarks demonstrate at least 5x throughput improvement for large replays

### Task 4: Dispatch Scheduling API Extension (API Extension)

External scheduling systems need programmatic access to AtlasDispatch's berth allocation and dispatch planning capabilities. Currently, these operations are only available through internal function calls with no structured API contract.

Extend the allocator module to expose a comprehensive scheduling API that supports batch dispatch planning, berth slot reservation, and capacity forecasting. The API should follow RESTful conventions and include request validation, rate limiting integration, and structured error responses with actionable error codes.

**Acceptance Criteria:**
- DispatchPlanRequest and DispatchPlanResponse types define the API contract with JSON tags
- Batch dispatch endpoint accepts up to 1,000 orders per request with pagination for results
- Berth reservation API supports tentative holds with configurable expiration times
- Capacity forecast endpoint returns projected availability for a specified time window
- All API operations integrate with the existing RateLimiter for throttling protection
- Validation errors return structured responses with field-level error details
- Async batch submissions return a job ID for status polling and result retrieval
- API versioning header support enables future backward-incompatible changes

### Task 5: Policy Engine State Migration (Migration)

The current policy engine stores operational mode state in memory with a simple string-based representation. A new compliance requirement mandates that policy state transitions be persisted to durable storage with full audit history, and that policy levels support hierarchical scoping (global, regional, and port-specific overrides).

Migrate the policy engine to a new hierarchical policy model where policies can be defined at multiple scopes with inheritance rules. Child scopes inherit parent policies unless explicitly overridden. The migration must be backward compatible: existing policy configurations should automatically map to global-scope policies, and all existing API calls should continue to work without modification.

**Acceptance Criteria:**
- PolicyScope type defines hierarchy levels: Global, Regional, Port, Terminal
- Hierarchical policy lookup returns the most specific applicable policy for a given context
- Existing single-scope policies are automatically migrated to Global scope on first access
- Policy inheritance can be overridden with explicit "inherit: false" configuration
- Conflict detection identifies when child policies would escalate beyond parent restrictions
- Audit history includes scope information for all policy state transitions
- PolicyEngine API maintains backward compatibility with single-scope callers
- Migration can be performed incrementally without system downtime

## Getting Started

```bash
go test -v ./...
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
