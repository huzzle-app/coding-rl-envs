# IronFleet - Alternative Tasks

## Overview

These 5 alternative development tasks extend IronFleet's fleet management platform with new features, performance optimizations, and architectural improvements. Each task focuses on a specific aspect: real-time convoy tracking, route consolidation, queue optimization, telemetry integration, and event sourcing migration.

## Environment

- **Language**: Go
- **Infrastructure**: Internal packages for core logic (allocator, routing, resilience, queue, policy, security, statistics, workflow), service layer for cross-service communication, shared contracts for topology
- **Difficulty**: Apex-Principal (1250 bugs across production codebase)

## Tasks

### Task 1: Real-Time Convoy Position Tracking (Feature Development)

Implement real-time position tracking capabilities that integrate with existing routing and analytics modules. Position updates must feed into health metrics and anomaly detection, with checkpoint semantics for replay recovery. Position update frequency respects policy engine state (normal: 30s, watch: 15s, restricted: 60s, halted: disabled).

### Task 2: Consolidate Route Selection Logic (Refactoring)

Unify fragmented route selection logic across routing, gateway, and service packages into a single `RouteSelector` interface. Remove duplicate sorting implementations while maintaining deterministic behavior for identical inputs. Gateway node selection must delegate to the unified routing layer.

### Task 3: Optimize Queue Shedding Performance (Performance Optimization)

Improve algorithmic efficiency of queue operations, reducing time complexity of bulk drain operations and implementing lazy health status computation with caching. Target 3x throughput improvement for 10,000-item queues while maintaining thread-safety and shedding semantics.

### Task 4: External Telemetry Integration API (API Extension)

Expose internal fleet health metrics, vessel distributions, queue depths, and policy states via standardized telemetry API. Support filtering by time range, vessel ID, and metric type with circuit breaker protection. Integrate with checkpoint manager for replay recovery.

### Task 5: Event Sourcing Migration for Dispatch Orders (Migration)

Migrate dispatch order allocation from mutable state to event-sourced model with immutable event stream capture. Support complete audit trails and point-in-time recovery. Maintain backward compatibility with existing dispatch APIs during migration period.

## Getting Started

```bash
go test -race -v ./...
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
