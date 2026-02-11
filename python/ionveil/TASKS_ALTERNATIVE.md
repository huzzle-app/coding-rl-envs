# IonVeil - Alternative Tasks

Beyond debugging, these tasks test feature development, refactoring, optimization, API extension, and migration capabilities within the policy enforcement and dispatch domain.

---

## Task 1: Feature Development - Cascading Policy Overrides

**Type:** Feature Development

**Description:**
Implement a hierarchical policy override system that allows zone-level and agency-level policies to cascade while respecting priority ordering. Currently, policies are applied globally without considering organizational hierarchy. The new system should support policy inheritance where child zones can override parent policies, but only for less restrictive rules.

For example, if a regional policy sets "restricted" mode, a local zone cannot override to "normal" but can escalate to "halted". The system must track override sources for audit purposes and automatically revert overrides when the parent policy de-escalates.

**Acceptance Criteria:**
- New `PolicyHierarchy` class manages parent-child policy relationships
- Zone policies inherit from parent unless explicitly overridden
- Child zones can only escalate (not de-escalate) relative to parent policy
- Override audit trail records source, timestamp, and authorization
- Automatic override cleanup when parent policy de-escalates below override level
- Thread-safe policy resolution for concurrent zone queries
- Policy hierarchy changes propagate to all child zones within 100ms

**Test Command:**
```bash
python tests/run_all.py -k policy_hierarchy
```

---

## Task 2: Refactoring - Unified Queue Health Monitor

**Type:** Refactoring

**Description:**
The queue health monitoring logic is currently scattered across `ionveil/queue.py`, `ionveil/statistics.py`, and `services/analytics/metrics.py`. Each module independently calculates health metrics with slightly different threshold logic and status labels. Extract this into a unified `QueueHealthMonitor` service that provides consistent health assessment across the entire system.

The refactored design should consolidate all threshold comparisons, status categorization, and alert triggering into a single source of truth. This includes the utilization thresholds (warning at 60%, critical at 80%), response time percentile calculations, and backpressure detection. Views and services should delegate to this monitor rather than implementing their own health checks.

**Acceptance Criteria:**
- New `QueueHealthMonitor` class in `ionveil/monitoring.py`
- All queue health logic consolidated: utilization, wait time estimation, backpressure
- Single threshold configuration source with environment variable overrides
- Consistent status labels across all monitoring endpoints
- Monitor is stateless and injectable for testing
- Existing API responses maintain backward compatibility
- All health-related tests continue to pass without modification

**Test Command:**
```bash
python tests/run_all.py -k queue
```

---

## Task 3: Performance Optimization - Batch Dispatch Planning

**Type:** Performance Optimization

**Description:**
The current `plan_dispatch` function in `ionveil/dispatch.py` processes orders individually, resulting in O(N log N) sorting for every dispatch request. For high-volume periods with 10,000+ pending orders across multiple agencies, this creates dispatch latency spikes exceeding SLA targets.

Optimize the dispatch planning to use incremental sorting with a priority heap structure. The system should maintain a pre-sorted order pool that accepts new orders in O(log N) time and can extract the top K orders for dispatch in O(K log N) time. Additionally, implement order coalescing to reduce redundant recalculations when multiple agencies request dispatches within a short time window.

**Acceptance Criteria:**
- Dispatch planning for 10,000 orders completes in under 50ms
- New order insertion maintains O(log N) complexity
- Batch extraction for multi-agency dispatch in single operation
- Order coalescing window configurable (default 100ms)
- Memory usage under 100MB for 50,000 order pool
- Dispatch order priority remains identical to current algorithm
- Add benchmark test validating performance requirements under load

**Test Command:**
```bash
python tests/run_all.py -k dispatch_performance
```

---

## Task 4: API Extension - Multi-Channel Route Failover

**Type:** API Extension

**Description:**
Add a multi-channel failover API that allows dispatch requests to specify backup routing channels. When the primary channel is blocked or exceeds latency thresholds, the system should automatically attempt the next channel in the failover chain. Currently, dispatchers must manually retry with different channels when primary routing fails.

The API should support weighted failover preferences, per-channel circuit breakers, and aggregated latency tracking across the failover chain. Failed primary attempts should be logged with reasons to support post-incident analysis and channel reliability scoring.

**Acceptance Criteria:**
- New endpoint `POST /dispatch/route/failover` accepts primary and backup channel list
- Automatic failover when primary channel latency exceeds threshold (configurable)
- Per-channel circuit breaker integration prevents cascading failures
- Failover attempt logging with channel, latency, and failure reason
- Response includes which channel succeeded and failover chain execution summary
- Maximum 3 failover attempts per request (configurable)
- Graceful degradation when all channels fail with detailed error response
- Channel reliability score updated based on failover patterns

**Test Command:**
```bash
python tests/run_all.py -k route_failover
```

---

## Task 5: Migration - Event Sourcing for Workflow State

**Type:** Migration

**Description:**
Migrate the `WorkflowEngine` from direct state mutation to an event-sourced architecture. Currently, entity states are stored directly and history is an append-only log that can diverge from the actual state. The new design should derive current state entirely from the event stream, enabling point-in-time state reconstruction and reliable event replay.

The migration must preserve all existing entity states and history records. New events should be stored with sequence numbers, causation IDs, and correlation IDs for distributed tracing. The system should support snapshotting for entities with long event histories (1000+ transitions) to optimize state reconstruction time.

**Acceptance Criteria:**
- New `WorkflowEventStore` class persists events as the source of truth
- Entity state derived from event stream replay
- Point-in-time state reconstruction via `get_state_at(entity_id, timestamp)`
- Automatic snapshotting for entities exceeding 1000 events
- Events include sequence_number, causation_id, and correlation_id
- Migration script converts existing state and history to events
- State reconstruction from 10,000 events completes in under 200ms
- All existing workflow tests pass against event-sourced implementation

**Test Command:**
```bash
python tests/run_all.py -k workflow
```
