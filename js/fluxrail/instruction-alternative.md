# FluxRail - Alternative Tasks

## Overview

These alternative tasks provide different entry points into the FluxRail codebase. Each task focuses on a specific aspect of the rail/transit dispatch system and requires understanding of the existing architecture. You can choose to implement features, refactor existing code, optimize performance, extend the API, or migrate to a new architectural pattern.

## Environment

- **Language**: JavaScript (Node)
- **Test Runner**: `node --test` (TAP format)
- **Infrastructure**: Docker Compose with 15 integrated modules
- **Difficulty**: Hyper-Principal
- **Constraint**: Do not edit files under `tests/`

## Tasks

### Task 1: Multi-Modal Connection Planning (Feature Development)

FluxRail currently handles single-modal dispatch routing, but stakeholders require support for multi-modal journey planning where freight or passengers transfer between rail lines, buses, and last-mile delivery vehicles. The system needs to compute optimal transfer points considering connection windows, platform proximity, and cumulative delay propagation.

Implement a connection planning module that calculates feasible transfer sequences between modes. The planner must respect minimum connection times (which vary by hub type), track cumulative delay risk across legs, and reject plans where any transfer window falls below safety thresholds. When multiple transfer options exist at a hub, the system should prefer connections that minimize total journey time while maintaining a configurable buffer for operational resilience.

The feature must integrate with the existing dispatch priority system so that high-priority freight receives preferential treatment in transfer slot allocation, and connection failures should trigger appropriate escalation through the policy engine.

### Task 2: Dispatch Engine Consolidation (Refactoring)

The dispatch logic is currently spread across multiple modules: `dispatch.js` handles route selection, `routing.js` manages hub assignment, `capacity.js` controls load balancing, and `queue.js` handles priority scoring. This distribution leads to duplicated concepts (priority appears in both dispatch and queue), inconsistent sorting behaviors, and difficulty reasoning about the complete dispatch flow.

Refactor the dispatch-related functionality to establish clear module boundaries with explicit contracts. Route selection should depend on hub selection (not vice versa), capacity constraints should inform dispatch decisions through a defined interface, and priority calculation should occur in exactly one location. The queue module should consume priority values rather than recomputing them.

The refactoring must maintain backward compatibility for all public module interfaces while improving internal cohesion. Any shared data structures (like congestion maps or capacity snapshots) should flow through well-defined parameters rather than relying on implicit module-level state.

### Task 3: Real-Time Congestion Response Optimization (Performance Optimization)

The current hub selection and route choice algorithms perform full sorts of congestion and latency data on every dispatch decision. During peak operations with hundreds of active hubs and thousands of in-flight dispatches, this creates measurable latency in the dispatch hot path. Operations has reported that dispatch decisions occasionally exceed the 50ms SLA during surge periods.

Optimize the congestion-aware routing to maintain sub-linear performance characteristics. Consider maintaining sorted data structures that update incrementally as congestion reports arrive, or implementing approximate selection algorithms that find near-optimal choices without full enumeration. The optimization must preserve correctness: the selected hub and route should be optimal (or within a configurable tolerance of optimal) for the given congestion snapshot.

The solution should also address the churn rate calculation, which currently iterates all keys on every computation. For large tenant partition maps, this becomes a bottleneck during rebalancing operations.

### Task 4: External Scheduling System Integration (API Extension)

FluxRail needs to integrate with external crew scheduling and maintenance planning systems. These systems require programmatic access to dispatch plans, capacity forecasts, and SLA breach predictions. The integration should expose a query interface for downstream consumers without coupling them to FluxRail's internal data structures.

Extend the system to provide read-only query capabilities for: active dispatch plans with their assignments and priority breakdowns, projected capacity availability windows, current and forecasted SLA breach risks by route corridor, and economic metrics including margin ratios and budget pressure indicators. The interface should support filtering by time window, route, hub, and severity level.

Query responses must reflect the current system state accurately, including any in-flight replay operations. The interface should include appropriate pagination for large result sets and provide stable cursors for incremental synchronization patterns used by external systems.

### Task 5: Event Sourcing Migration (Migration)

The current replay system maintains state through in-memory accumulation with periodic checkpoints. Operations requires a full event-sourcing architecture where all dispatch state changes are captured as immutable events, enabling point-in-time reconstruction, audit queries, and parallel projection computation.

Migrate the state management to an event-sourced model. Each dispatch decision, capacity rebalance, policy override, and SLA breach should produce an event that fully describes the state transition. The system must support rebuilding current state by replaying events from any checkpoint, with idempotency guarantees that produce identical results regardless of replay timing or ordering within version boundaries.

The migration must handle the transition period where both old checkpoint-based and new event-sourced state coexist. Existing replay chaos tests should continue to pass, validating that the event-sourced model maintains the same consistency guarantees as the current implementation.

## Getting Started

```bash
cd js/fluxrail
npm install
npm test
```

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). All 8,053 tests must pass without modification to test files.
