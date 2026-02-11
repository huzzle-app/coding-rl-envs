# PolarisCore - Alternative Tasks

These tasks represent common engineering challenges in the PolarisCore logistics and polar operations platform. Each task focuses on a specific aspect of the cold-chain control plane.

---

## Task 1: Multi-Zone Fulfillment Window Scheduling (Feature Development)

### Description

The current allocation system treats all fulfillment windows as independent time slots without consideration for geographic zones. Operations teams have requested the ability to define fulfillment windows that span multiple polar zones (e.g., Arctic-A, Arctic-B, Antarctic-C), where each zone may have different capacity constraints and operational temperatures.

The feature should allow shipments to be allocated across zone-specific windows while respecting zone-level capacity limits and ensuring that high-priority shipments can preempt lower-priority allocations when zone capacity is constrained. The system must also support "thermal bridging" where shipments transitioning between zones with significant temperature differentials require additional buffer capacity.

This enhancement is critical for Q4 operations when multiple research stations require coordinated supply deliveries across the polar regions.

### Acceptance Criteria

- Extend the `FulfillmentWindow` model to include a `zone` field representing the geographic polar zone
- Implement zone-aware allocation that respects per-zone capacity limits independently
- Support thermal bridging capacity requirements when shipments move between zones with temperature differences exceeding 15 degrees Celsius
- High-priority shipments (priority >= 8) can preempt lower-priority allocations within the same zone when capacity is exhausted
- Allocation reports must include zone-level utilization metrics
- Maintain backward compatibility with existing single-zone allocation workflows
- All existing tests continue to pass
- New tests validate multi-zone allocation scenarios

### Test Command

```bash
cargo test
```

---

## Task 2: Risk Assessment Pipeline Refactoring (Refactoring)

### Description

The risk assessment logic in the policy module has grown organically and now exhibits several code quality issues. The `risk_score` function combines load calculations, incident severity weighting, and thermal boundary checks in a single monolithic function. This makes it difficult to test individual risk components, extend the scoring algorithm, or apply different risk models for different shipment types.

The risk assessment pipeline should be refactored into a composable architecture where each risk component (load risk, incident risk, thermal risk) is evaluated independently and can be weighted or replaced based on operational requirements. The refactored design should support adding new risk factors (e.g., geopolitical risk, weather forecast risk) without modifying existing code.

Additionally, the relationship between `risk_score`, `requires_hold`, and `compliance_tier` should be formalized through a unified risk assessment result type that encapsulates the score, hold decision, and compliance classification together.

### Acceptance Criteria

- Extract load risk calculation into a separate, testable function
- Extract incident risk calculation into a separate, testable function
- Extract thermal risk calculation into a separate, testable function
- Create a `RiskAssessment` struct that combines score, hold requirement, and compliance tier
- Implement a `RiskAssessor` trait that allows pluggable risk calculation strategies
- Refactor `orchestrate_cycle` to use the new risk assessment architecture
- All risk calculations must produce identical results to the current implementation
- No changes to the public API signatures of existing functions
- All existing tests continue to pass without modification

### Test Command

```bash
cargo test
```

---

## Task 3: Queue Processing Performance Optimization (Performance Optimization)

### Description

Production monitoring has identified that the queue ordering algorithm becomes a bottleneck during peak operations when processing queues with 10,000+ items. The current implementation recalculates priority weights for every comparison during sorting, leading to O(n log n) weight calculations when a single O(n) precomputation pass would suffice.

Additionally, the `queue_pressure` calculation iterates through the queue twice (once for severity sum, once for wait sum) when a single pass could compute both values. For large queues during incident response, this doubles the processing time unnecessarily.

The statistics module's `percentile` and `rolling_sla` functions are also called frequently in tight loops during SLA monitoring. These functions should be optimized to minimize allocations and improve cache locality for the common case of computing multiple percentiles from the same dataset.

### Acceptance Criteria

- Precompute priority weights before sorting to eliminate redundant calculations during comparisons
- Combine severity and wait time summation into a single iteration pass
- Implement an optimized percentile calculation that reuses sorted data for multiple percentile queries
- Add a `PercentileCalculator` struct that pre-sorts data once and supports efficient multiple percentile lookups
- Reduce memory allocations in `rolling_sla` by avoiding intermediate collections
- Benchmark tests must demonstrate at least 2x improvement for queue operations with 10,000 items
- All existing tests continue to pass
- No changes to function signatures or return values

### Test Command

```bash
cargo test
```

---

## Task 4: Shipment Tracking Event API Extension (API Extension)

### Description

External logistics partners require programmatic access to shipment tracking events through a structured API. The current system maintains internal event contracts but lacks a comprehensive API for querying shipment history, subscribing to status updates, and retrieving aggregate tracking metrics.

The API extension should expose shipment lifecycle events (intake, allocation, routing, fulfillment, delivery) with full audit trail information. Partners need the ability to query events by shipment ID, time range, event type, or originating service. The API must also support real-time event streaming for active shipments and batch export for historical analysis.

Security requirements mandate that all API responses include cryptographic signatures for data integrity verification, and that sensitive fields (exact coordinates, internal service identifiers) are redacted based on the caller's authorization level.

### Acceptance Criteria

- Define a `TrackingEvent` struct with fields for event ID, shipment ID, timestamp, event type, service origin, and payload
- Implement event query functions supporting filters by shipment ID, time range, and event type
- Add event aggregation functions for computing shipment transit time, dwell time per hub, and service latency metrics
- All API responses must include a cryptographic signature using the existing `simple_signature` mechanism
- Implement field-level redaction that removes sensitive data based on a provided authorization context
- Support pagination for event queries returning more than 100 results
- All existing tests continue to pass
- New tests validate event querying, aggregation, and security features

### Test Command

```bash
cargo test
```

---

## Task 5: Replay System Migration to Event Sourcing (Migration)

### Description

The current resilience module uses a simple replay budget calculation that does not preserve the full event history needed for audit compliance. Regulatory requirements now mandate that all shipment decisions be fully reconstructible from an immutable event log. The system must migrate from the current stateless replay approach to a proper event sourcing architecture.

The migration involves introducing an event store abstraction that captures all state-changing operations as immutable events. The existing `retry_backoff`, `replay_budget`, and `failover_region` functions must be reimplemented to work with the event-sourced model, where replay operations reconstruct state by replaying the event log rather than recalculating from scratch.

The event sourcing implementation must support point-in-time state reconstruction, event versioning for schema evolution, and snapshot optimization for long-running shipment lifecycles. The migration must be performed incrementally without disrupting ongoing operations.

### Acceptance Criteria

- Define an `Event` trait with methods for event type, timestamp, and payload serialization
- Implement an `EventStore` trait supporting append, query by aggregate ID, and query by time range
- Create concrete event types for allocation decisions, routing selections, policy evaluations, and failover triggers
- Implement state reconstruction by replaying events from a given point in time
- Add snapshot support that persists aggregate state periodically to optimize replay performance
- Support event versioning with upcasting for backward-compatible schema changes
- Migrate `failover_region` to emit and consume events rather than operating statelessly
- All existing tests continue to pass
- New tests validate event persistence, replay correctness, and snapshot optimization

### Test Command

```bash
cargo test
```
