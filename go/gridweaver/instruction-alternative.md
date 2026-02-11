# GridWeaver - Alternative Tasks

## Overview

Five alternative challenge tasks that extend GridWeaver's capabilities through feature development, refactoring, performance optimization, API design, and event-driven architecture migration. Each task tests different software engineering disciplines while leveraging the same smart-grid orchestration codebase.

## Environment

- **Language**: Go
- **Infrastructure**: Distributed smart-grid platform with NATS JetStream, PostgreSQL, Redis, InfluxDB, and etcd
- **Difficulty**: Ultra-Principal (8-threshold reward)

## Tasks

### Task 1: Feature Development - Multi-Region Cascade Dispatch ([Feature](./TASKS_ALTERNATIVE.md#task-1-feature-development---multi-region-cascade-dispatch))

Implement cross-regional power transfer capabilities that allow the system to automatically source supplemental power from neighboring regions when a region experiences generation shortfall. The cascade dispatch must traverse the topology graph, respect transmission constraints, apply transfer loss factors, and integrate with the consensus mechanism to prevent split-brain scenarios.

### Task 2: Refactoring - Unified Event Pipeline with Back-Pressure ([Refactoring](./TASKS_ALTERNATIVE.md#task-2-refactoring---unified-event-pipeline-with-back-pressure))

Consolidate fragmented event handling across multiple packages into a unified event pipeline that provides consistent deduplication, configurable windowing, and built-in back-pressure signaling. Refactor existing event functions to become composable pipeline stages while preserving backward compatibility and adding metrics hooks for observability.

### Task 3: Performance Optimization - Parallel Topology Analysis ([Optimization](./TASKS_ALTERNATIVE.md#task-3-performance-optimization---parallel-topology-analysis))

Optimize the topology analysis subsystem to support concurrent operations using fine-grained locking or lock-free structures. Parallelize path-finding to explore multiple routes simultaneously, leverage the worker pool for capacity calculations, and reduce memory allocations in hot paths using sync.Pool. Target at least 3x improvement for large graphs (1000+ nodes) with all race detection tests passing.

### Task 4: API Extension - Real-Time Demand Response Bidding ([API](./TASKS_ALTERNATIVE.md#task-4-api-extension---real-time-demand-response-bidding))

Design and implement a bidding API that allows external demand response participants to submit price-based bids for load reduction. The system must evaluate bids by cost-effectiveness while considering participant reliability scores, handle concurrent submissions safely, and integrate bid decisions with the existing dispatch and audit services.

### Task 5: Migration - Event Sourcing for Dispatch History ([Migration](./TASKS_ALTERNATIVE.md#task-5-migration---event-sourcing-for-dispatch-history))

Migrate the dispatch system to an event-sourcing architecture where all operations are recorded as immutable events. Implement event types for dispatch plans, constraints, and demand response decisions, create a projection mechanism to rebuild state from events, support replay for any point in time, and maintain backward compatibility with the existing synchronous API.

## Getting Started

```bash
docker compose up -d
go test -race -v ./...
bash harbor/test.sh
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). All code must pass race detection tests and follow existing GridWeaver patterns for error handling, logging, and metrics.
