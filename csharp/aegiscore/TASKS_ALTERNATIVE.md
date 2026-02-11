# AegisCore - Alternative Tasks

This document provides alternative task specifications for the AegisCore security platform. Each task focuses on a different aspect of software engineering while staying within the security and access control domain.

---

## Task 1: Role-Based Access Control (RBAC) Feature Development

**Type:** Feature Development

### Description

AegisCore currently handles security through token validation and origin allowlisting, but lacks a comprehensive role-based access control system. The platform needs an RBAC implementation that integrates with the existing `Security` and `Policy` modules to provide fine-grained permission management for dispatch operations.

The new RBAC system should define roles such as `operator`, `supervisor`, `admin`, and `auditor` with distinct permission sets. Operators can submit and view dispatch orders but cannot modify policy settings. Supervisors can escalate/de-escalate policies manually. Admins have full system access including security configuration. Auditors have read-only access to all workflow history and audit logs.

The implementation must integrate seamlessly with the existing `TokenStore` for session management and the `PolicyEngine` for policy-gated operations. Role assignments should be persisted and validated on every sensitive operation across the `Allocator`, `QueueGuard`, and `Workflow` modules.

### Acceptance Criteria

- Define a `Role` enum or record type with at least four distinct roles: `Operator`, `Supervisor`, `Admin`, `Auditor`
- Implement a `PermissionSet` that maps roles to allowed operations (e.g., `SubmitOrder`, `ViewQueue`, `ModifyPolicy`, `AccessAuditLog`)
- Create a `RoleStore` class that associates user/token IDs with assigned roles
- Integrate role checks into `PolicyEngine.Escalate` and `PolicyEngine.Deescalate` methods
- Add role validation to `Allocator.PlanDispatch` for order submission authorization
- Ensure `WorkflowEngine.Transition` validates caller has appropriate role for state changes
- Implement `AuditLog` access controls that restrict sensitive transition records to authorized roles
- All existing tests must continue to pass

**Test Command:** `dotnet test`

---

## Task 2: Queue Management Module Refactoring

**Type:** Refactoring

### Description

The `QueueGuard` module has grown organically and now contains multiple responsibilities: load shedding decisions, wait time estimation, priority queue management, rate limiting, and health monitoring. This violates the single responsibility principle and makes the code difficult to test and maintain independently.

The module should be refactored into distinct, focused components following clean architecture principles. Each component should have a clear interface, minimal dependencies on other components, and be independently testable. The refactoring should not change the external behavior of the system.

The priority queue implementation currently uses a simple `List<T>` with sorting on every insert, which is inefficient for high-throughput scenarios. As part of the refactoring, consider whether the internal data structure choices are appropriate for a production security platform handling thousands of dispatch requests.

### Acceptance Criteria

- Extract `LoadShedder` as a separate static class handling only shedding decisions based on depth, limits, and emergency status
- Extract `WaitTimeEstimator` as a separate static class for queue wait time calculations
- Refactor `PriorityQueue<T>` to use a heap-based implementation for O(log n) enqueue operations
- Create an `IQueueHealthProvider` interface implemented by `QueueHealthMonitor`
- Ensure `RateLimiter` is decoupled from queue depth concerns and focuses solely on token bucket logic
- Maintain backward compatibility: all public method signatures in `QueueGuard` namespace must remain unchanged
- Document the new component boundaries with XML documentation comments
- All existing tests must continue to pass

**Test Command:** `dotnet test`

---

## Task 3: Circuit Breaker Performance Optimization

**Type:** Performance Optimization

### Description

The `CircuitBreaker` class in the `Resilience` module uses coarse-grained locking that serializes all state transitions. In high-concurrency scenarios where thousands of dispatch requests flow through the system, this becomes a bottleneck. Performance profiling has shown lock contention on the circuit breaker as a significant contributor to request latency.

The current implementation also recalculates state on every `RecordSuccess` and `RecordFailure` call. For burst traffic patterns common in maritime dispatch (e.g., a convoy of vessels arriving simultaneously), this creates unnecessary overhead when the circuit is in a stable state.

Optimize the `CircuitBreaker` implementation to reduce lock contention and improve throughput without compromising thread safety or the correctness of state transitions. Consider lock-free techniques, read-write locks, or state caching strategies appropriate for the access patterns.

### Acceptance Criteria

- Replace the coarse `lock` with `ReaderWriterLockSlim` or implement lock-free state transitions using `Interlocked` operations
- Implement lazy state evaluation that avoids unnecessary threshold checks when the circuit is in a stable `Closed` state
- Add a `RecordBatch(int successCount, int failureCount)` method for efficient bulk updates during high-throughput periods
- Ensure state transitions remain atomic and thread-safe under concurrent access
- Add a `GetStatistics()` method returning success/failure counts without acquiring write locks
- Benchmark before/after: demonstrate at least 2x throughput improvement under 100 concurrent callers
- Ensure the `CheckpointManager.ShouldCheckpoint` integration continues to work correctly
- All existing tests must continue to pass

**Test Command:** `dotnet test`

---

## Task 4: Security Event Notification API Extension

**Type:** API Extension

### Description

AegisCore's security module handles token validation, path sanitization, and origin checking, but lacks a notification mechanism for security events. Security teams need real-time visibility into authentication failures, potential path traversal attempts, policy escalations, and suspicious queue behavior patterns.

Extend the existing modules to emit security events that can be consumed by external monitoring systems. The API should support multiple notification channels (in-memory for testing, webhook for production) and provide filtering capabilities to reduce noise for high-volume deployments.

The event schema should capture sufficient context for security incident response: timestamp, event type, severity, source module, affected entity IDs, and relevant metadata. Events should be designed for compatibility with SIEM (Security Information and Event Management) systems.

### Acceptance Criteria

- Define a `SecurityEvent` record with fields: `Timestamp`, `EventType`, `Severity`, `SourceModule`, `EntityId`, `Metadata` dictionary
- Create a `SecurityEventType` enum covering: `TokenValidationFailed`, `TokenExpired`, `PathTraversalAttempted`, `OriginBlocked`, `PolicyEscalated`, `QueueShedding`, `CircuitOpened`
- Implement an `ISecurityEventSink` interface with `Emit(SecurityEvent)` method
- Create an `InMemoryEventSink` implementation for testing that stores last N events
- Add event emission points in `TokenStore.Validate`, `Security.SanitisePath`, `Security.IsAllowedOrigin`, `PolicyEngine.Escalate`, `QueueGuard.ShouldShed`, and `CircuitBreaker.RecordFailure`
- Implement an `EventFilter` class that can filter events by type, severity, or source module
- Ensure event emission does not block the critical path (fire-and-forget pattern or async)
- All existing tests must continue to pass

**Test Command:** `dotnet test`

---

## Task 5: In-Memory to Redis Token Store Migration

**Type:** Migration

### Description

The current `TokenStore` implementation uses an in-memory dictionary with lock-based synchronization. This works for single-instance deployments but does not support horizontal scaling. When multiple AegisCore instances run behind a load balancer, tokens issued by one instance are not visible to others, causing authentication failures.

Migrate the `TokenStore` to support Redis as a backing store while maintaining backward compatibility with the in-memory implementation for development and testing. The migration should introduce an abstraction layer that allows runtime configuration of the storage backend.

Consider the operational requirements: token cleanup (TTL handling), atomic operations for concurrent access, graceful degradation if Redis becomes unavailable, and connection pooling for efficient resource usage.

### Acceptance Criteria

- Define an `ITokenStore` interface with methods: `Store`, `Validate`, `Revoke`, `Cleanup`, and `Count` property
- Refactor the existing `TokenStore` to implement `ITokenStore` as `InMemoryTokenStore`
- Create a `RedisTokenStore` implementation that uses Redis strings with TTL for automatic expiration
- Implement `TokenStoreFactory` that creates the appropriate implementation based on configuration
- Add connection pooling and retry logic for Redis operations with configurable timeouts
- Implement graceful fallback: if Redis is unavailable, log warning and deny validation (fail-closed security)
- Ensure `Cleanup` is a no-op for Redis (relies on native TTL) but works for in-memory
- Add integration test scaffolding that can run against a Redis container
- All existing tests must continue to pass using the in-memory implementation

**Test Command:** `dotnet test`

---
