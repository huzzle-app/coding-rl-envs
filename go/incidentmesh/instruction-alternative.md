# IncidentMesh - Alternative Tasks

## Overview

IncidentMesh presents 5 alternative tasks that test different software engineering skills within a Go-based emergency response coordination platform. These tasks focus on feature development, architectural refactoring, performance optimization, API extension, and system migration.

## Environment

- **Language**: Go 1.21+
- **Infrastructure**: Global emergency response coordination platform with 13 microservices and 10 internal packages
- **Difficulty**: Ultra-Principal

## Tasks

### Task 1: Feature Development — Multi-Tier Escalation Policies

Implement a sophisticated escalation policy engine that supports configurable escalation rules accounting for time-of-day, responder fatigue, and cross-region coverage. Organizations need escalation chains that vary based on incident severity, time since report, and current responder availability. The policy engine must integrate seamlessly with existing triage and routing systems while maintaining backward compatibility with single-threshold escalation.

### Task 2: Refactoring — Event Pipeline Architecture

Refactor the event processing implementation from a simple stage-based pipeline into a pluggable handler architecture. Each event type should implement a common interface, with middleware-style interceptors for cross-cutting concerns like logging, metrics, and deduplication. Centralize event correlation logic to make adding new event types a matter of implementing a single handler interface rather than modifying multiple files.

### Task 3: Performance Optimization — Concurrent Dispatch Orchestration

Optimize dispatch orchestration to leverage Go's concurrency primitives effectively for handling mass-casualty events with hundreds of rapid unit assignments. Address bottlenecks in routing score calculations and capacity checks through worker pool implementation, parallel fan-out operations, and throttling mechanisms. Focus on atomic operations and safe counter implementations to prevent race conditions under high load.

### Task 4: API Extension — Real-Time Capacity Federation

Extend the capacity API to support real-time capacity federation across regional dispatch centers. Implement a federated capacity model with leader-elected coordinator, capacity normalization for heterogeneous resource types, and graceful degradation during network partitions. Support both synchronous queries and subscription-based updates for real-time capacity monitoring.

### Task 5: Migration — Unified Routing Subsystem

Consolidate routing-related logic scattered across multiple packages into a unified routing subsystem with clear separation between route calculation, route selection, and route execution. Migrate ETA estimation, distance scoring, capacity filtering, and region matching into cohesive components while preserving all existing routing behavior and supporting pluggable routing strategies.

## Getting Started

```bash
# Run all tests (verbose, race detector)
go test -race -v ./...

# Verify with Harbor
bash harbor/test.sh
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md), which specifies detailed requirements for each task including function signatures, interface contracts, and integration points with existing IncidentMesh components.
