# NimbusFlow - Alternative Tasks

## Overview

NimbusFlow supports five alternative tasks that test feature development, refactoring, and optimization skills. These tasks exercise the codebase's core capabilities around checkpoint management, rate limiting, route optimization, priority overrides, and event sourcing patterns.

## Environment

- **Language**: Kotlin 1.9
- **Infrastructure**: Maven-based build with JUnit 5 tests, Docker support
- **Difficulty**: Hyper-Principal (70-140h)

## Tasks

### Task 1: Checkpoint Recovery (Feature)

Implement a workflow checkpoint recovery system that enables resuming workflows from their last successful checkpoint rather than restarting from the beginning. The recovery system should detect incomplete workflows, locate their most recent checkpoint, and integrate with the WorkflowEngine and policy-based escalation controls to prevent cascading recovery attempts during system failures.

### Task 2: Unified Rate Limiting (Refactor)

Refactor the rate limiting infrastructure to provide a unified strategy coordinating token bucket admission with queue depth shedding. This eliminates the dual-approach inconsistency where requests might pass rate limiting but get shed at the queue. The refactored solution maintains backward compatibility with existing APIs while internally routing through the unified strategy.

### Task 3: Route Selection Caching (Optimize)

Optimize route selection performance by implementing intelligent caching that memoizes route selection results and channel scores. The cache should be invalidated when routes are added/removed or when scoring parameters change, with configurable TTLs based on route stability. This reduces redundant filtering, sorting, and calculation overhead in the routing layer.

### Task 4: Priority Override API (Feature)

Extend the dispatch allocation API to support time-bounded priority overrides that can elevate or suppress specific orders relative to their calculated priority. Overrides require authorization tracking and are restricted by policy escalation states. The system should prevent abuse through override limits and minimum intervals between changes.

### Task 5: Event Sourcing Migration (Refactor)

Migrate the event replay infrastructure to a full event sourcing pattern using an append-only event log. The migration supports point-in-time state reconstruction and integrates with checkpoint snapshots to prevent unbounded log growth. Both existing replay behavior and new event sourcing queries remain supported during the transition.

## Getting Started

```bash
./gradlew test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
