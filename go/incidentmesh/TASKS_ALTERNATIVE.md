# IncidentMesh Alternative Tasks

These alternative tasks provide different entry points into the IncidentMesh codebase, each focusing on a specific type of software engineering work within the incident management domain.

---

## Task 1: Feature Development — Multi-Tier Escalation Policies

### Description

IncidentMesh currently supports basic escalation level calculation based on priority thresholds. Emergency response organizations need more sophisticated escalation policies that account for time-of-day, responder fatigue, and cross-region coverage gaps.

Implement a multi-tier escalation policy engine that supports configurable escalation rules. The engine should allow organizations to define escalation chains that vary based on incident severity, time since report, and current responder availability. For example, a critical cardiac event during night shift should escalate faster than a minor incident during peak staffing hours. The policy engine must integrate with the existing triage and routing systems.

The feature should support policy composition, where multiple policies can be combined with AND/OR logic. Escalation decisions should be auditable, with full traceability of which policy rules triggered each escalation level change.

### Acceptance Criteria

- Policy engine accepts configurable escalation rules with severity, time, and availability conditions
- Escalation chains support time-based acceleration (faster escalation for higher severity or longer wait times)
- Cross-region escalation triggers when local responder pool drops below configurable threshold
- Policy decisions are logged to the compliance audit trail with rule identifiers
- Backward compatibility maintained: existing single-threshold escalation continues to work
- All escalation policy tests pass with the new implementation
- Integration tests verify policy composition with AND/OR rule combinations

### Test Command

```bash
go test -v ./...
```

---

## Task 2: Refactoring — Event Pipeline Architecture

### Description

The current event processing implementation in IncidentMesh uses a simple stage-based pipeline that applies transformations sequentially. This architecture has become difficult to maintain as new event types and correlation requirements have been added. The event handling code is scattered across multiple packages with inconsistent patterns.

Refactor the event pipeline to use a pluggable handler architecture. Each event type should have a dedicated handler that implements a common interface. The pipeline should support middleware-style interceptors for cross-cutting concerns like logging, metrics, and deduplication. Event correlation logic should be centralized rather than duplicated across handlers.

The refactoring should consolidate event filtering, windowing, and correlation into a coherent event processing subsystem. The goal is to make adding new event types a matter of implementing a single handler interface rather than modifying multiple files.

### Acceptance Criteria

- Event handlers implement a common interface with Process(event) and CanHandle(eventType) methods
- Pipeline supports registering multiple handlers for the same event type
- Middleware interceptors can be inserted before/after handler execution
- Event correlation is centralized in a single CorrelationService
- Deduplication logic is extracted into a reusable middleware
- All existing event processing tests continue to pass
- New handler registration requires no changes to pipeline core code
- Event windowing supports configurable time boundaries (inclusive/exclusive)

### Test Command

```bash
go test -v ./...
```

---

## Task 3: Performance Optimization — Concurrent Dispatch Orchestration

### Description

IncidentMesh dispatch orchestration currently processes incident assignments sequentially, which creates bottlenecks during mass-casualty events when hundreds of units need rapid assignment. Profiling shows that the routing score calculations and capacity checks dominate execution time.

Optimize the dispatch orchestration to leverage Go's concurrency primitives effectively. The worker pool implementation needs to handle variable workloads without creating resource contention. Fan-out operations for multi-region routing should execute in parallel while maintaining correctness. Throttling must be implemented to prevent overwhelming downstream capacity services during surge conditions.

Critical attention is needed for the atomic operations and safe counter implementations, as race conditions have been reported under high load. The optimization should maintain the existing API contracts while improving throughput by at least 10x for batch dispatch operations.

### Acceptance Criteria

- Worker pool enforces minimum size and handles dynamic scaling
- Fan-out operations correctly pass indices to parallel tasks
- Safe counter uses proper atomic operations to prevent race conditions
- Throttle function respects maximum concurrency limits
- Channel merge operations drain all values, not just one per channel
- Atomic max operations use compare-and-swap for correctness
- Pipeline stages execute in the correct order (first to last)
- All concurrency tests pass, including stress tests with race detector

### Test Command

```bash
go test -race -v ./...
```

---

## Task 4: API Extension — Real-Time Capacity Federation

### Description

IncidentMesh needs to support real-time capacity federation across regional dispatch centers. Currently, capacity information is queried synchronously, which introduces latency and stale data issues when coordinating multi-region incident response.

Extend the capacity API to support a federated capacity model where regional centers publish their current capacity to a shared state. The federation should use a leader-elected coordinator to prevent split-brain scenarios where two regions both believe they own the same resources. Capacity normalization must handle heterogeneous resource types (ambulances, helicopters, hospital beds) with different units and thresholds.

The API should expose both synchronous queries for immediate capacity checks and subscription-based updates for real-time capacity monitoring. Partition detection should gracefully degrade to local-only capacity when network splits occur.

### Acceptance Criteria

- Capacity federation API supports publish/subscribe model for regional capacity
- Leader election correctly identifies coordinator across nodes
- Lease management properly renews expiry times (now + duration, not just now)
- Split-brain detection triggers when more than one leader exists
- Term comparison returns correct ordering (+1 for greater, -1 for lesser)
- Heartbeat checking correctly computes elapsed time (now - lastBeat)
- State merge selects the higher-term state during leadership transitions
- Step-down operation properly clears the leader flag
- Partition detection uses majority threshold (total/2) for quorum decisions

### Test Command

```bash
go test -v ./...
```

---

## Task 5: Migration — Unified Routing Subsystem

### Description

IncidentMesh has accumulated routing logic across multiple packages, with some calculations in the internal routing module, others in the routing service, and still others embedded in dispatch orchestration. This fragmentation has led to inconsistent routing decisions and makes it difficult to implement new routing algorithms.

Migrate all routing-related logic into a unified routing subsystem with clear separation between route calculation (algorithms), route selection (policy), and route execution (dispatch). The migration should consolidate ETA estimation, distance scoring, capacity filtering, and region matching into cohesive components. Batch routing should correctly assign units based on each incident's region rather than using a single unit for all.

The unified subsystem should support pluggable routing strategies (nearest-first, load-balanced, priority-based) without changing the core routing infrastructure. All existing routing behavior must be preserved through the migration.

### Acceptance Criteria

- Nearest unit selection returns the unit with minimum ETA, not maximum
- Route score correctly penalizes distance (subtract, not add)
- Region filtering includes matching regions, not excludes them
- Multi-region routing keeps the best unit per region (lowest ETA)
- ETA estimation converts hours to minutes with proper ceiling
- Capacity filtering uses >= for threshold (includes exact matches)
- Sorting by ETA produces ascending order (fastest first)
- Batch routing assigns units based on each incident's specific region
- Distance scoring rejects or handles negative distances appropriately
- Route optimization applies region filter before selecting nearest unit

### Test Command

```bash
go test -v ./...
```
