# OpalCommand - Alternative Tasks

## Overview

Five alternative development tasks for the OpalCommand maritime command and control platform, focusing on feature development, performance optimization, and architectural refactoring. Each task independently improves specific subsystems without requiring bug fixes.

## Environment

- **Language**: Ruby
- **Infrastructure**: Docker Compose with Redis, PostgreSQL, Kafka; shared contracts service registry; 21 modules with 9,263+ tests
- **Difficulty**: Apex-Principal

## Tasks

### Task 1: Command Batching and Coalescing (Feature Development)

Implement a command batching system that coalesces related commands before dispatch. Group commands by vessel identifier and berth zone with a configurable 500ms time window. Commands with different priority levels should not be coalesced, and critical-priority commands should bypass batching entirely. Maintain command ordering guarantees within each batch and preserve original submission timestamps for audit purposes. When dispatched, emit a single consolidated command payload to reduce gateway fanout overhead.

### Task 2: Corridor Table Index Optimization (Refactoring)

Refactor the CorridorTable class to maintain secondary indices for common access patterns. Add a region-based index for O(1) lookups when selecting routes by geographic region, and an activity index that separates active and inactive corridors. Indices must be maintained atomically with primary storage under mutex protection. Preserve the existing public API while internally restructuring data storage, maintaining all thread-safety guarantees.

### Task 3: Settlement Decay Rate Caching (Performance Optimization)

Implement a memoization layer for the settlement service's berth_decay_rate calculation. Cache results using a composite key normalized to 2 decimal places, with LRU eviction policy and configurable maximum cache size (default 1000 entries). Cache invalidation should occur when berth configuration changes are detected. Must be thread-safe without introducing lock contention that negates performance gains, achieving at least 10x performance improvement for repeated calculations.

### Task 4: Workflow State Machine Extension API (API Extension)

Implement a state machine extension API allowing runtime registration of custom states and transitions. Support registering new states with validation to prevent conflicts with existing core states. Custom states must be prefixed with "x_" and can reference core terminal states but cannot modify core transitions. Provide introspection methods returning the combined graph (core plus extensions) for tooling integration. Tenant-specific extensions override global extensions in conflict resolution.

### Task 5: Event Store Migration to Append-Only Log (Migration)

Migrate the resilience module from in-memory hash storage to an append-only event log preserving complete history. Maintain an index of the latest sequence number per event ID for efficient replay while enabling historical queries. Implement log compaction with retention policy (keep events from last 24 hours or last 1000 events per ID, whichever is larger). Provide idempotent migration utility converting existing checkpoint data without service interruption.

## Getting Started

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
