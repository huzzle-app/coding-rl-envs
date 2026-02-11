# TransitCore - Alternative Tasks

## Overview

These alternative tasks represent realistic feature development, refactoring, and optimization work for the TransitCore intermodal dispatch and capacity command platform. Each task develops different software engineering skills while leveraging the existing codebase architecture.

## Environment

- **Language**: Java 21
- **Build**: Maven + JUnit 5
- **Infrastructure**: PostgreSQL, Redis, NATS
- **Difficulty**: Principal

## Tasks

### Task 1: Multi-Modal Transfer Coordination (Feature Development)

Extend TransitCore to handle coordinated multi-modal transfers where passengers or freight switch between different transit modes (bus-to-rail, rail-to-ferry, etc.) at designated transfer hubs. The dispatch planning system must calculate optimal transfer times accounting for mode-specific dwell times, platform walking distances, and historical delay patterns. Implement hold-or-release decisions based on passenger impact and downstream SLA effects.

### Task 2: Extract Queue Management Domain (Refactoring)

Consolidate scattered queue governance logic across QueueGovernor, CapacityBalancer, and ResilienceReplay into a cohesive domain module. Refactor queue-related decisions (admission control, throttling, shedding, backpressure) into explicit state machine representations while preserving all existing behavior and maintaining backward compatibility.

### Task 3: Dispatch Decision Caching (Performance Optimization)

Implement a caching layer for route selection and hub assignment computations that currently become bottlenecks during peak hours. Add memoization with composite keys based on origin, destination, and time window, with intelligent cache invalidation triggered by network topology changes and capacity threshold crossings. Optimize dispatch latency P95 by at least 40% for repeated similar requests.

### Task 4: Fleet Telemetry Ingestion API (API Extension)

Develop a streaming telemetry API that accepts high-frequency vehicle position, speed, occupancy, and status updates to replace periodic batch updates. The API must handle out-of-order delivery, deduplicate messages, and integrate telemetry into routing heuristics for live travel time estimation and into the capacity balancer for real-time available capacity tracking.

### Task 5: Event Sourcing Migration for Dispatch State (Migration)

Migrate dispatch state management from direct mutations to an event-sourced model where all state transitions are captured as immutable events. Preserve backward compatibility with existing integrations, integrate with the compliance ledger for retention policies, and support zero-downtime deployment with dual-write mode during the transition period.

## Getting Started

```bash
cd java/transitcore
mvn test -q
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) for the selected task.
