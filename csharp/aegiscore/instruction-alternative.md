# AegisCore - Alternative Tasks

## Overview

AegisCore supports five alternative engineering tasks beyond debugging: RBAC feature development, queue module refactoring for clean architecture, circuit breaker performance optimization for high-concurrency scenarios, security event notification API extension, and a production-scale token store migration from in-memory to Redis.

## Environment

- **Language**: C# 12 / .NET 8
- **Infrastructure**: Maritime dispatch reliability platform with eight interconnected services (Allocator, Routing, Policy, QueueGuard, Security, Resilience, Statistics, Workflow)
- **Difficulty**: Hyper-Principal

## Tasks

### Task 1: Role-Based Access Control (RBAC) Feature Development (Feature)

Implement a comprehensive RBAC system that integrates with the existing `Security` and `Policy` modules. Define roles (`Operator`, `Supervisor`, `Admin`, `Auditor`) with distinct permission sets, create a `RoleStore` for persistence, and integrate role validation into `PolicyEngine`, `Allocator.PlanDispatch`, and `WorkflowEngine.Transition`. The system must maintain backward compatibility while providing fine-grained permission management across dispatch operations.

### Task 2: Queue Management Module Refactoring (Refactoring)

Refactor the `QueueGuard` module to follow the single responsibility principle by extracting `LoadShedder`, `WaitTimeEstimator`, and `IQueueHealthProvider` as separate focused components. Replace the simple `List<T>` priority queue with a heap-based implementation for O(log n) enqueue operations. Maintain all existing public method signatures for backward compatibility while improving maintainability and testability.

### Task 3: Circuit Breaker Performance Optimization (Optimization)

Optimize the `CircuitBreaker` class to reduce lock contention in high-concurrency scenarios. Replace coarse-grained `lock` with `ReaderWriterLockSlim` or lock-free `Interlocked` operations, implement lazy state evaluation for stable states, add a `RecordBatch` method for bulk updates, and implement `GetStatistics()` for lock-free reads. Demonstrate at least 2x throughput improvement under 100 concurrent callers.

### Task 4: Security Event Notification API Extension (API Extension)

Extend the security module with a real-time event notification mechanism. Define a `SecurityEvent` record and `SecurityEventType` enum, implement `ISecurityEventSink` with `InMemoryEventSink` for testing, add event emission points across `TokenStore`, `Security`, `PolicyEngine`, `QueueGuard`, and `CircuitBreaker`, and implement an `EventFilter` class for event filtering. Fire-and-forget pattern ensures non-blocking operation.

### Task 5: In-Memory to Redis Token Store Migration (Migration)

Migrate the `TokenStore` from in-memory dictionary to a Redis-backed implementation while maintaining backward compatibility. Define an `ITokenStore` interface, refactor existing implementation as `InMemoryTokenStore`, create `RedisTokenStore` with TTL support and connection pooling, implement `TokenStoreFactory` for runtime configuration selection, and provide graceful degradation if Redis becomes unavailable.

## Getting Started

```bash
cd csharp/aegiscore && dotnet test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). Choose one or more tasks to implement. Each task requires all existing tests to continue passing while adding new functionality or architectural improvements.
