# TensorForge - Alternative Tasks

## Overview

TensorForge supports 5 alternative task types beyond the core debugging challenge. These tasks test feature development, refactoring, performance optimization, API design, and concurrency modernization using the same codebase and infrastructure.

## Environment

- **Language**: Rust (edition 2021)
- **Infrastructure**: PostgreSQL 15, Redis 7 (Docker Compose)
- **Difficulty**: Apex-Principal
- **Codebase**: 14 source modules covering allocation, routing, policy, resilience, security, workflow, statistics, and more

## Tasks

### Task 1: Tensor Computation Batch Scheduler (Feature Development)

Implement a batch scheduling system that groups compatible tensor computation requests based on model type, tensor dimensions, and priority levels. The batch scheduler must support dynamic batch sizing based on available GPU memory, configurable maximum batch wait times to balance latency versus throughput, and priority-aware batching that ensures high-priority inference requests are not delayed by lower-priority batch accumulation.

Integration with existing queue management infrastructure and policy escalation framework is required. Batch-level statistics including average batch fill rate, batch processing latency percentiles, and throughput metrics must feed into the telemetry pipeline.

**Test Command**: `cargo test batch_scheduler`

### Task 2: Workflow State Machine Refactoring (Refactoring)

Refactor the WorkflowEngine to separate concerns using cleaner architecture. Extract the state machine definition into a dedicated StateMachine trait, create a TransitionValidator abstraction for implementing custom validation rules, and separate audit logging into an AuditSink trait.

The refactoring must maintain backward compatibility with existing code using WorkflowEngine directly. All existing transition semantics must be preserved, and the transition history format must remain unchanged for downstream analytics systems compatibility.

**Test Command**: `cargo test workflow`

### Task 3: Statistics Computation Performance Optimization (Performance Optimization)

Optimize the statistics module for high-throughput scenarios. The percentile calculation currently sorts the entire dataset on every call; implement an incremental quantile estimation algorithm that can maintain approximate percentiles with bounded memory. Moving average computation creates intermediate vectors; optimize to compute in-place with streaming updates.

For correlation and covariance calculations, implement blocked algorithms that improve cache locality when processing large arrays. The ResponseTimeTracker sliding window should use a ring buffer to avoid shifting elements on every insertion.

**Test Command**: `cargo test statistics`

### Task 4: Inference Request Routing API Extension (API Extension)

Extend the routing module to support model-aware routing, A/B testing traffic splits, shadow traffic for model validation, and geographic affinity routing. Implement a RoutingPolicy trait encapsulating routing decisions with built-in implementations for latency-based, round-robin, weighted, and model-affinity routing.

Add support for traffic splitting where a percentage of requests route to experimental model versions. Implement shadow routing that duplicates requests to validation endpoints without affecting response latency. Support route annotations for passing model metadata through the routing layer.

**Test Command**: `cargo test routing`

### Task 5: Queue System Migration to Lock-Free Implementation (Migration)

Migrate the PriorityQueue and RateLimiter from Mutex-based synchronization to lock-free implementations using atomic operations and compare-and-swap primitives. The migration must preserve the existing public API to avoid breaking downstream code.

Implement a lock-free priority queue and an atomic token bucket for the RateLimiter. Special attention is required for the queue drain operation which must atomically snapshot and clear the queue. The migration must maintain linearizability guarantees so that concurrent operations appear to occur in a valid sequential order.

**Test Command**: `cargo test queue`

## Getting Started

```bash
# Start Docker dependencies
docker compose up -d

# Run tests to see current state
cargo test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).

- Feature/Refactor/Optimize tasks: All specified tests pass
- Migration/API tasks: Public API unchanged, backward compatibility maintained
- Performance optimization: Numerical accuracy within 1% of exact computation
