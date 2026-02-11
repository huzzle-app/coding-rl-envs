# OpalCommand - Alternative Tasks

This document describes alternative development tasks for the OpalCommand command and control platform. Each task can be completed independently and focuses on different aspects of the system.

---

## Task 1: Command Batching and Coalescing (Feature Development)

### Description

The OpalCommand intake service currently processes commands individually, which creates overhead when multiple commands target the same vessel or berth within a short time window. Implement a command batching system that coalesces related commands before dispatch.

The batching system should group commands by vessel identifier and berth zone, applying a configurable time window (default 500ms) for accumulation. Commands with different priority levels should not be coalesced, and critical-priority commands should bypass batching entirely. The system must maintain command ordering guarantees within each batch and preserve the original submission timestamps for audit purposes.

When a batch is dispatched, the system should emit a single consolidated command payload containing all coalesced operations, reducing gateway fanout overhead and improving settlement throughput during high-traffic periods.

### Acceptance Criteria

- Commands targeting the same vessel within the batch window are coalesced into a single dispatch payload
- Commands with different priorities are never merged into the same batch
- Critical priority commands bypass batching and are dispatched immediately
- Original command timestamps are preserved in the batch metadata for audit compliance
- Batch dispatch latency does not exceed the configured time window plus 50ms processing overhead
- Empty batches are never dispatched (edge case when all commands are cancelled before window expires)
- Batch size limits are enforced (maximum 50 commands per batch) with overflow creating new batches
- Gateway admission control receives accurate aggregate load values for batched commands

### Test Command

```bash
bundle exec rspec spec/services/intake_service_spec.rb spec/core/dispatch_spec.rb
```

---

## Task 2: Corridor Table Index Optimization (Refactoring)

### Description

The CorridorTable class in the routing module stores route information keyed by channel name, but operations like filtering active corridors and selecting by region require full table scans. Refactor the CorridorTable to maintain secondary indices for common access patterns.

Add a region-based index that groups corridors by their geographic region, enabling O(1) lookups when selecting routes for regional dispatch. Implement an activity index that separates active and inactive corridors, eliminating the need to filter the entire table when building route chains. The indices must be maintained atomically with the primary storage to prevent inconsistencies during concurrent access.

The refactoring should preserve the existing public API while internally restructuring data storage. All existing mutex protections must remain in place, and the thread-safety guarantees of the original implementation must not be weakened.

### Acceptance Criteria

- Region-based lookups return corridors for a specific region in O(1) time complexity
- Active corridor enumeration no longer requires filtering the full table
- Adding, updating, and removing corridors updates all indices atomically under mutex protection
- The existing public API (add, get, remove, all, count, active) remains unchanged
- Memory overhead from indices does not exceed 2x the base storage requirement
- Concurrent access from multiple threads produces consistent results
- Index consistency is maintained even when operations fail mid-update (rollback semantics)

### Test Command

```bash
bundle exec rspec spec/core/routing_spec.rb spec/integration/routing_integration_spec.rb
```

---

## Task 3: Settlement Decay Rate Caching (Performance Optimization)

### Description

The settlement service's berth_decay_rate calculation is invoked frequently during congestion prediction and berth utilization reporting. The calculation involves multiple floating-point operations that produce deterministic results for the same input parameters. Implement a memoization layer to cache decay rate computations.

The cache should use a composite key derived from berth length, area, and mass parameters, with the key normalized to avoid floating-point comparison issues (round to 2 decimal places before key generation). Implement an LRU eviction policy with a configurable maximum cache size (default 1000 entries) to bound memory consumption during extended operation.

Cache invalidation should occur when berth configuration changes are detected through the reconcile service. The caching layer must be thread-safe and should not introduce lock contention that would negate performance gains under high concurrency.

### Acceptance Criteria

- Repeated calls with identical parameters return cached results without recalculation
- Cache keys are normalized to 2 decimal places to handle floating-point input variations
- LRU eviction removes least-recently-used entries when cache exceeds maximum size
- Cache hit rate is exposed via a statistics method for monitoring integration
- Thread-safe access allows concurrent reads without blocking
- Cache invalidation API allows the reconcile service to clear stale entries
- Performance improvement of at least 10x for repeated calculations with same parameters
- Memory usage stays bounded regardless of input variety

### Test Command

```bash
bundle exec rspec spec/services/settlement_service_spec.rb spec/services/reconcile_service_spec.rb
```

---

## Task 4: Workflow State Machine Extension API (API Extension)

### Description

The workflow module's state machine is currently defined as a frozen constant, making it impossible to extend for custom vessel types or experimental dispatch flows without modifying core code. Implement a state machine extension API that allows runtime registration of custom states and transitions.

The extension API should support registering new states with their allowed transitions, validating that extensions do not conflict with existing core states. Custom states must be clearly namespaced (prefixed with "x_") to distinguish them from platform-defined states. Extensions can reference core states in their transitions (e.g., a custom state can transition to the core "cancelled" state) but cannot modify core state transitions.

Provide introspection methods that return the combined graph (core plus extensions) for tooling integration. Extensions should be registered per-tenant or globally, with tenant-specific extensions taking precedence in conflict resolution.

### Acceptance Criteria

- New states can be registered at runtime with allowed transitions
- Custom states must be prefixed with "x_" and are validated on registration
- Extensions can define transitions from custom states to core terminal states
- Core state definitions remain immutable and cannot be modified by extensions
- Combined graph introspection returns merged core and extension state machines
- Tenant-scoped extensions override global extensions for the same custom state
- Invalid extension registrations (circular references, invalid state names) are rejected with descriptive errors
- WorkflowEngine correctly uses the extended graph for entities registered with custom initial states

### Test Command

```bash
bundle exec rspec spec/core/workflow_spec.rb spec/integration/workflow_integration_spec.rb
```

---

## Task 5: Event Store Migration to Append-Only Log (Migration)

### Description

The resilience module currently stores replay events in an in-memory hash structure that overwrites entries by ID. Migrate to an append-only event log that preserves the complete history of all events, enabling temporal queries and forensic analysis of command sequences.

The append-only log should support efficient replay by maintaining an index of the latest sequence number per event ID, allowing the existing replay semantics to be preserved while also enabling historical queries. Implement log compaction that removes superseded events during maintenance windows, controlled by a retention policy (default: keep events from the last 24 hours or the last 1000 events per ID, whichever is larger).

Provide a migration utility that converts existing checkpoint data to the new log format without service interruption. The migration must be idempotent to handle restart scenarios during long-running conversions.

### Acceptance Criteria

- Events are stored in append-only fashion with monotonically increasing log positions
- Latest-event-per-ID index enables O(1) lookups for current state queries
- Replay method returns the same results as the original implementation for compatibility
- Historical query API retrieves all events for an ID within a time range
- Log compaction removes superseded events while preserving retention policy requirements
- Migration utility converts existing checkpoint data without data loss
- Migration is idempotent and can be safely re-run after interruption
- Write throughput does not degrade significantly (within 20% of original) after migration

### Test Command

```bash
bundle exec rspec spec/core/resilience_spec.rb spec/integration/replay_integration_spec.rb
```
