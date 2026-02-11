# FluxRail - Alternative Tasks

These alternative tasks provide different entry points into the FluxRail codebase. Each task focuses on a specific aspect of the rail/transit dispatch system and requires understanding of the existing architecture.

---

## Task 1: Multi-Modal Connection Planning (Feature Development)

FluxRail currently handles single-modal dispatch routing, but stakeholders require support for multi-modal journey planning where freight or passengers transfer between rail lines, buses, and last-mile delivery vehicles. The system needs to compute optimal transfer points considering connection windows, platform proximity, and cumulative delay propagation.

Implement a connection planning module that calculates feasible transfer sequences between modes. The planner must respect minimum connection times (which vary by hub type), track cumulative delay risk across legs, and reject plans where any transfer window falls below safety thresholds. When multiple transfer options exist at a hub, the system should prefer connections that minimize total journey time while maintaining a configurable buffer for operational resilience.

The feature must integrate with the existing dispatch priority system so that high-priority freight receives preferential treatment in transfer slot allocation, and connection failures should trigger appropriate escalation through the policy engine.

**Acceptance Criteria:**
- Connection plans calculate minimum viable transfer times based on hub configuration
- Cumulative delay risk propagates correctly across all journey legs
- Transfer window validation rejects plans with insufficient buffer time
- High-priority dispatches receive preferential connection slot allocation
- Connection failures integrate with the existing policy escalation system
- Multi-leg journeys produce accurate total cost projections through the economics module
- All existing tests continue to pass (`npm test`)

**Test Command:** `npm test`

---

## Task 2: Dispatch Engine Consolidation (Refactoring)

The dispatch logic is currently spread across multiple modules: `dispatch.js` handles route selection, `routing.js` manages hub assignment, `capacity.js` controls load balancing, and `queue.js` handles priority scoring. This distribution leads to duplicated concepts (priority appears in both dispatch and queue), inconsistent sorting behaviors, and difficulty reasoning about the complete dispatch flow.

Refactor the dispatch-related functionality to establish clear module boundaries with explicit contracts. Route selection should depend on hub selection (not vice versa), capacity constraints should inform dispatch decisions through a defined interface, and priority calculation should occur in exactly one location. The queue module should consume priority values rather than recomputing them.

The refactoring must maintain backward compatibility for all public module interfaces while improving internal cohesion. Any shared data structures (like congestion maps or capacity snapshots) should flow through well-defined parameters rather than relying on implicit module-level state.

**Acceptance Criteria:**
- Priority calculation occurs in a single authoritative location
- Route selection explicitly depends on hub selection results
- Capacity constraints integrate through a defined interface, not implicit coupling
- Sorting logic uses consistent comparison semantics across all dispatch-related modules
- Public module exports remain backward compatible
- No circular dependencies exist between dispatch-related modules
- All 8,053 tests pass without modification to test files

**Test Command:** `npm test`

---

## Task 3: Real-Time Congestion Response Optimization (Performance Optimization)

The current hub selection and route choice algorithms perform full sorts of congestion and latency data on every dispatch decision. During peak operations with hundreds of active hubs and thousands of in-flight dispatches, this creates measurable latency in the dispatch hot path. Operations has reported that dispatch decisions occasionally exceed the 50ms SLA during surge periods.

Optimize the congestion-aware routing to maintain sub-linear performance characteristics. Consider maintaining sorted data structures that update incrementally as congestion reports arrive, or implementing approximate selection algorithms that find near-optimal choices without full enumeration. The optimization must preserve correctness: the selected hub and route should be optimal (or within a configurable tolerance of optimal) for the given congestion snapshot.

The solution should also address the churn rate calculation, which currently iterates all keys on every computation. For large tenant partition maps, this becomes a bottleneck during rebalancing operations.

**Acceptance Criteria:**
- Hub selection operates in sub-linear time relative to hub count for steady-state operations
- Route selection avoids full sort when congestion data has not materially changed
- Churn rate calculation scales efficiently with partition map size
- Dispatch decisions remain optimal (or within 5% of optimal) compared to exhaustive search
- Memory overhead of any caching structures remains bounded
- Performance improvement is measurable in the stress test suite
- All correctness tests continue to pass

**Test Command:** `npm test`

---

## Task 4: External Scheduling System Integration (API Extension)

FluxRail needs to integrate with external crew scheduling and maintenance planning systems. These systems require programmatic access to dispatch plans, capacity forecasts, and SLA breach predictions. The integration should expose a query interface for downstream consumers without coupling them to FluxRail's internal data structures.

Extend the system to provide read-only query capabilities for: active dispatch plans with their assignments and priority breakdowns, projected capacity availability windows, current and forecasted SLA breach risks by route corridor, and economic metrics including margin ratios and budget pressure indicators. The interface should support filtering by time window, route, hub, and severity level.

Query responses must reflect the current system state accurately, including any in-flight replay operations. The interface should include appropriate pagination for large result sets and provide stable cursors for incremental synchronization patterns used by external systems.

**Acceptance Criteria:**
- Dispatch plan queries return accurate assignment counts and priority distributions
- Capacity availability projections account for queued demand and reserve floors
- SLA breach risk queries correctly reflect current ETA calculations and buffer configurations
- Economic metric queries expose margin ratios and budget pressure with appropriate precision
- Results can be filtered by time window, route corridor, hub, and severity
- Pagination with stable cursors supports large result set traversal
- Query results remain consistent during concurrent replay operations
- All existing functionality continues to work correctly

**Test Command:** `npm test`

---

## Task 5: Event Sourcing Migration (Migration)

The current replay system maintains state through in-memory accumulation with periodic checkpoints. Operations requires a full event-sourcing architecture where all dispatch state changes are captured as immutable events, enabling point-in-time reconstruction, audit queries, and parallel projection computation.

Migrate the state management to an event-sourced model. Each dispatch decision, capacity rebalance, policy override, and SLA breach should produce an event that fully describes the state transition. The system must support rebuilding current state by replaying events from any checkpoint, with idempotency guarantees that produce identical results regardless of replay timing or ordering within version boundaries.

The migration must handle the transition period where both old checkpoint-based and new event-sourced state coexist. Existing replay chaos tests should continue to pass, validating that the event-sourced model maintains the same consistency guarantees as the current implementation.

**Acceptance Criteria:**
- All state-changing operations produce immutable events with sufficient detail for replay
- State can be reconstructed from any checkpoint by replaying subsequent events
- Idempotency keys prevent duplicate event application regardless of replay timing
- Event version ordering is preserved across distributed replay scenarios
- Ledger balance calculations remain accurate under event-sourced reconstruction
- Existing chaos and resilience tests pass without modification
- Migration supports gradual rollout with old and new state models coexisting
- No data loss occurs during the migration transition period

**Test Command:** `npm test`
