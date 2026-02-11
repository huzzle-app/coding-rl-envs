# TransitCore - Alternative Tasks

These alternative tasks represent realistic feature development, refactoring, and optimization work for the TransitCore intermodal dispatch and capacity command platform.

---

## Task 1: Multi-Modal Transfer Coordination (Feature Development)

### Description

TransitCore currently handles single-mode dispatches but lacks support for coordinated multi-modal transfers where passengers or freight must switch between different transit modes (bus-to-rail, rail-to-ferry, etc.) at designated transfer hubs. The dispatch planning system needs to be extended to handle transfer windows, connection guarantees, and fallback routing when primary connections are missed.

The feature must calculate optimal transfer times accounting for mode-specific dwell times, platform walking distances, and historical delay patterns. When a feeder service is running late, the system should evaluate whether to hold the connecting service (based on passenger impact and downstream SLA effects) or reroute affected passengers to alternative connections.

Transfer coordination must integrate with the existing capacity balancer to prevent overloading connecting services and with the SLA model to track end-to-end journey SLAs rather than just segment SLAs.

### Acceptance Criteria

- Multi-leg journeys can be planned with specified transfer points and minimum connection times
- Transfer windows are validated against real-time arrival predictions from feeder services
- Hold-or-release decisions are computed based on passenger count, downstream capacity, and SLA impact
- Missed connection scenarios trigger automatic rebooking to next available service
- Capacity reservations cascade properly across all legs of multi-modal journeys
- End-to-end SLA tracking aggregates segment delays with transfer buffer consumption
- Transfer hub congestion is factored into routing heuristics for hub selection
- Audit trail captures all hold decisions with reasoning and approval chain

### Test Command

```bash
mvn test
```

---

## Task 2: Extract Queue Management Domain (Refactoring)

### Description

The queue governance logic is currently spread across multiple components: QueueGovernor handles policy selection and throttling decisions, CapacityBalancer manages shedding and rebalancing, and ResilienceReplay contains retry backoff calculations. This scattered responsibility makes it difficult to reason about queue behavior holistically and has led to subtle inconsistencies in how different components handle boundary conditions.

Refactor the queue management concerns into a cohesive domain module that encapsulates all queue-related decisions: admission control, throttling, shedding, backpressure signaling, and recovery. The new structure should make the relationship between queue depth, inflight count, failure rates, and policy transitions explicit and testable.

This refactoring should preserve all existing behavior while improving testability and making it easier to add new queue policies (e.g., priority lanes, deadline-aware scheduling) in the future.

### Acceptance Criteria

- Queue admission, throttling, and shedding logic is consolidated into a single domain module
- Policy transitions (normal -> degraded -> shed) have explicit state machine representation
- Backoff calculations for retries and replays use a shared strategy to ensure consistency
- Queue metrics (depth, inflight, wait time percentiles) are computed in one place
- Circuit breaker state is integrated with queue policy selection
- All existing test assertions pass without modification to test logic
- New integration tests verify coordinated behavior across queue operations
- No changes to public API signatures of existing components

### Test Command

```bash
mvn test
```

---

## Task 3: Dispatch Decision Caching (Performance Optimization)

### Description

Route selection and hub assignment computations are currently performed on every dispatch request, even when the underlying network conditions and capacity states have not changed. During peak hours, the DispatchPlanner and RoutingHeuristics components become bottlenecks as they repeatedly compute the same optimal routes and hubs for similar origin-destination pairs.

Implement a caching layer for dispatch decisions that memoizes route selections and hub assignments based on relevant input state. The cache must be invalidated when network topology changes, when capacity thresholds cross significant boundaries, or when congestion patterns shift materially. Cache entries should have configurable TTLs based on route volatility.

The optimization must not compromise dispatch quality - stale cache entries must be detected and evicted before they cause suboptimal assignments. Implement cache hit rate and staleness metrics for operational visibility.

### Acceptance Criteria

- Route selection results are cached with composite keys based on origin, destination, and time window
- Hub assignment results are cached with keys incorporating current congestion bands
- Cache invalidation triggers on capacity threshold crossings (configurable boundaries)
- TTL-based expiration prevents serving stale routes during rapid network changes
- Cache bypass is available for time-critical dispatches requiring fresh computation
- Metrics expose cache hit rate, miss rate, and average staleness at eviction
- Dispatch latency P95 improves by at least 40% for repeated similar requests
- All routing correctness tests continue to pass with caching enabled

### Test Command

```bash
mvn test
```

---

## Task 4: Fleet Telemetry Ingestion API (API Extension)

### Description

TransitCore needs real-time fleet telemetry to make informed dispatch and capacity decisions, but currently relies on periodic batch updates from external systems. Extend the platform with a streaming telemetry API that accepts high-frequency vehicle position, speed, occupancy, and status updates. This data should feed into the routing heuristics for live travel time estimation and into the capacity balancer for real-time available capacity tracking.

The API must handle out-of-order delivery, duplicate messages (vehicle retransmissions), and variable reporting frequencies across different fleet segments. Telemetry events should be processed through the existing watermark window for late arrival handling and incorporated into the audit trail for incident reconstruction.

Design the API to support both push (webhook) and pull (polling) consumption patterns for downstream systems that need to react to fleet state changes.

### Acceptance Criteria

- REST endpoint accepts vehicle telemetry payloads with position, speed, occupancy, and status
- Telemetry events are deduplicated using vehicle ID and timestamp combination
- Out-of-order events within the skew tolerance window are accepted and ordered correctly
- Late-arriving events beyond the watermark are logged but excluded from live calculations
- Real-time occupancy feeds into capacity balancer for available seat calculations
- Live position and speed update travel time estimates in routing heuristics
- Webhook registration endpoint allows subscribing to fleet state change notifications
- Polling endpoint returns fleet state changes since a provided sequence number
- Telemetry ingestion rate is tracked in statistics reducer for capacity planning

### Test Command

```bash
mvn test
```

---

## Task 5: Event Sourcing Migration for Dispatch State (Migration)

### Description

The dispatch workflow currently maintains state through direct mutations, making it difficult to reconstruct historical states for audit, debugging, or replay scenarios. Migrate the dispatch state management to an event-sourced model where all state transitions are captured as immutable events that can be replayed to reconstruct any point-in-time state.

The migration must preserve backward compatibility with existing integrations that expect the current state query API. Event storage should integrate with the existing compliance ledger for retention policy enforcement and with the audit trail for fingerprinting and hash chaining. The resilience replay system should be updated to source from the event log rather than maintaining separate replay events.

Plan the migration to support zero-downtime deployment with a dual-write period where both old and new state representations are maintained until verification is complete.

### Acceptance Criteria

- All dispatch state transitions emit immutable events to a durable event store
- Point-in-time state reconstruction is possible by replaying events up to a target timestamp
- Existing state query APIs return results derived from event replay (or cached projections)
- Event retention follows compliance ledger policies (hot/warm/cold tiering by age)
- Event fingerprints and hash chains integrate with audit trail verification
- Resilience replay sources events from the unified event log
- Dual-write mode supports running old and new systems in parallel during migration
- Snapshot optimization prevents full replay for recent state queries
- All existing workflow and audit tests pass against the event-sourced implementation

### Test Command

```bash
mvn test
```
