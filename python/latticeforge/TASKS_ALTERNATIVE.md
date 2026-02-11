# LatticeForge - Alternative Tasks

These alternative tasks provide different ways to work with the LatticeForge service mesh platform. Each task focuses on a specific type of engineering work: feature development, refactoring, performance optimization, API extension, or migration.

---

## Task 1: Feature Development - Weighted Load Balancing with Health-Aware Routing

### Description

The current gateway service uses a simple scoring function to select route nodes based on latency, queue depth, and saturation. Production deployments have reported that during partial outages, traffic continues to flow to nodes that are technically "healthy" but operating at degraded capacity due to upstream dependencies.

Implement a weighted load balancing system that incorporates real-time health signals from the telemetry module. The system should track sliding-window health scores for each node, apply exponentially-weighted moving averages to smooth out transient failures, and adjust routing decisions based on both current metrics and recent health trends. The feature must integrate with the existing `RouteNode` dataclass and `select_primary_node` function without breaking existing callers.

Additionally, the system should support configurable "warmup" periods for nodes returning from maintenance, during which they receive reduced traffic proportionally until their health score stabilizes above a threshold.

### Acceptance Criteria

- Health-aware routing uses EWMA from the telemetry module to track per-node health trends over a configurable time window
- Nodes returning from degraded state undergo a warmup period (default 5 minutes) with reduced traffic allocation
- The `score_node` function incorporates health trend data alongside existing metrics (latency, queue depth, saturation)
- Warmup traffic allocation follows an exponential ramp: 10% at start, reaching 100% at end of warmup period
- Health scores below 0.3 trigger automatic node removal from candidate pool regardless of other metrics
- All existing gateway service tests continue to pass
- New unit tests cover health trend calculation, warmup period behavior, and degraded node exclusion

### Test Command

```bash
python tests/run_all.py
```

---

## Task 2: Refactoring - Extract Circuit Breaker Pattern from Resilience Service

### Description

The resilience service currently contains multiple interleaved concerns: failover region selection, replay budgeting, outage classification, and retry backoff calculation. These responsibilities have grown organically and now exhibit tight coupling that makes testing and maintenance difficult. The `build_replay_plan` function in particular orchestrates multiple steps that should be independently testable.

Refactor the resilience module to extract a standalone circuit breaker pattern implementation. The circuit breaker should manage state transitions (closed, open, half-open) based on failure rates, support configurable thresholds for trip conditions, and integrate cleanly with the existing failover logic. The refactored design should follow the single-responsibility principle, with each component handling one specific concern.

The refactoring must preserve all existing behavior while improving testability. After refactoring, each component (circuit breaker, failover selector, replay planner, backoff calculator) should be independently instantiable and testable without requiring the full service context.

### Acceptance Criteria

- Circuit breaker implementation with closed/open/half-open states and configurable failure thresholds
- State transition logic: closed->open after N failures in window, open->half-open after timeout, half-open->closed after success
- Failover region selection extracted to standalone class with explicit dependencies
- Replay plan builder refactored to compose smaller, single-purpose functions
- Each extracted component has its own dedicated test file
- No changes to public API signatures consumed by other services
- All existing resilience and chaos tests continue to pass
- Cyclomatic complexity of `build_replay_plan` reduced by at least 50%

### Test Command

```bash
python tests/run_all.py
```

---

## Task 3: Performance Optimization - Batch Processing Pipeline for Intake Service

### Description

The intake service processes incoming commands sequentially, validating each command, checking for duplicates, and sorting by urgency. Profiling has revealed that under high load (10,000+ commands per batch), the normalization pipeline becomes a bottleneck due to repeated dictionary lookups and linear scans for deduplication.

Optimize the intake service batch processing to handle high-throughput scenarios efficiently. The current `normalize_intake_batch` function performs O(n) work per item for deduplication and O(n log n) sorting at the end. For large batches, this results in unacceptable latency that causes upstream timeouts.

Implement a streaming batch processor that validates commands in parallel where possible, uses hash-based data structures for O(1) deduplication lookups, and maintains a sorted structure incrementally rather than sorting at the end. The optimization must preserve exactly the same output ordering and error semantics as the current implementation.

### Acceptance Criteria

- Batch normalization for 10,000 commands completes in under 100ms (current: ~800ms)
- Deduplication uses hash-based lookup with O(1) average case per command
- Validation errors are collected without blocking valid command processing
- Output ordering matches current behavior: sorted by (deadline, command_id)
- Memory usage for processing does not exceed 2x the input batch size
- All existing intake service tests pass with identical assertions
- New benchmark tests demonstrate performance improvement with various batch sizes (100, 1000, 10000)
- No changes to `IntakeCommand` dataclass or `validate_command_shape` function signature

### Test Command

```bash
python tests/run_all.py
```

---

## Task 4: API Extension - Rate Limiting and Quota Management for Gateway

### Description

The gateway service needs rate limiting capabilities to protect downstream services from traffic spikes. Currently, the `admission_control` function provides basic backpressure based on backlog and inflight counts, but it lacks per-tenant quotas, sliding window rate limits, and graduated throttling.

Extend the gateway API to support comprehensive rate limiting. The system should track request rates per operator organization, enforce configurable quotas per intent type, and provide graduated responses (delay, throttle, reject) based on quota utilization levels. Rate limits should be defined in the shared contracts module and enforced consistently across all gateway entry points.

The extension must support both hard limits (immediate rejection) and soft limits (delayed processing with exponential backoff). Quota state should be queryable for observability dashboards, and quota exhaustion should trigger notifications through the existing notification service integration.

### Acceptance Criteria

- Per-organization rate limiting with configurable requests-per-minute quotas defined in shared contracts
- Per-intent quotas supporting different limits for high-risk operations (e.g., `firmware-patch` vs `status-refresh`)
- Sliding window algorithm for rate calculation with 1-minute granularity
- Three-tier response: allow (under 70% quota), delay (70-90% quota with backoff), reject (over 90% quota)
- Quota state exposed via new `quota_status(org_id, intent)` function returning utilization percentage
- Integration with `NotificationPlanner` to alert on repeated quota exhaustion
- Admission control response includes quota-related fields: `quota_remaining`, `reset_seconds`, `throttle_ms`
- All existing gateway tests pass; new tests cover quota enforcement, sliding window accuracy, and notification triggers

### Test Command

```bash
python tests/run_all.py
```

---

## Task 5: Migration - Centralized Policy Engine with Rule-Based Evaluation

### Description

Policy evaluation logic is currently scattered across multiple services: `identity/service.py` handles authorization, `policy/service.py` manages risk gates, and individual services implement their own compliance checks. This distribution makes it difficult to audit policy decisions, update rules consistently, or add new compliance requirements.

Migrate to a centralized policy engine that consolidates all authorization, risk evaluation, and compliance checking into a unified rule-based system. The engine should support declarative policy rules defined in a configuration format, evaluate rules in priority order, and produce audit-ready decision logs.

The migration must be backward-compatible: existing service APIs must continue to work by delegating to the new policy engine. The engine should support policy versioning to enable gradual rollout and rollback of rule changes. All current policy decisions must produce identical outcomes after migration.

### Acceptance Criteria

- Centralized `PolicyEngine` class in `latticeforge/` that handles all authorization and compliance decisions
- Declarative rule format supporting conditions on: operator clearance, risk score, intent type, org membership
- Rule priority ordering with first-match-wins semantics and default deny
- Audit log output for every decision: rule matched, inputs evaluated, outcome, timestamp, trace_id
- Existing `authorize_intent`, `evaluate_policy_gate`, and `enforce_dual_control` functions delegate to policy engine
- Policy versioning: engine accepts version parameter to evaluate against historical rule sets
- Migration validation: side-by-side comparison mode that runs both old and new paths and logs discrepancies
- All existing policy, identity, and integration tests pass without modification
- New tests verify rule evaluation order, audit log completeness, and version rollback behavior

### Test Command

```bash
python tests/run_all.py
```
