# TensorForge - Apex-Principal Rust Reliability Platform

## Overview

TensorForge is a Rust-based realtime model-serving exchange control platform with **1270 deeply interconnected bugs** across 14 source modules. Bugs span configuration defaults, concurrency primitives, event ordering, security validation, data integrity, formula errors, and state machine logic. Many bugs have dependency chains (depth 3-8) with chained and diamond prerequisites.

## Architecture

14 source modules covering allocation, routing, policy, resilience, security, workflow, statistics, events, concurrency, config, telemetry, and contracts. 13 microservices with dependency DAG.

| Module | Focus | Lines |
|--------|-------|-------|
| `src/config.rs` | Service configuration, defaults, validation, feature flags | ~120 |
| `src/concurrency.rs` | Barriers, atomic counters, partitioning, cycle detection, work stealing | ~130 |
| `src/events.rs` | Timed event ordering, dedup, time windows, gap detection, batching | ~140 |
| `src/telemetry.rs` | Error rates, latency buckets, throughput, health scores, alerting | ~100 |
| `src/allocator.rs` | Order allocation, berth scheduling, cost estimation, capacity checks | ~220 |
| `src/contracts.rs` | Service definitions, topology, dependency analysis, health endpoints | ~190 |
| `src/models.rs` | Dispatch orders, vessel manifests, severity classification, ETA | ~160 |
| `src/policy.rs` | Policy escalation/deescalation, SLA compliance, risk scoring | ~210 |
| `src/queue.rs` | Priority queue, rate limiting, batch enqueue, fairness, pressure | ~220 |
| `src/resilience.rs` | Replay, circuit breaker, checkpoint, retry backoff, bulkhead | ~300 |
| `src/routing.rs` | Route selection, multi-leg planning, fuel efficiency, failover | ~170 |
| `src/security.rs` | Signing, token validation, password strength, permissions, IP filtering | ~180 |
| `src/statistics.rs` | Percentiles, weighted mean, EMA, normalization, correlation | ~230 |
| `src/workflow.rs` | State transitions, workflow engine, bottleneck analysis, audit | ~310 |

## Bug Categories

| Category | Examples |
|----------|----------|
| Boundary errors | `>` instead of `>=`, off-by-one in loops |
| Sort direction | Ascending vs descending, wrong comparator |
| Wrong constants | `0.3` should be `0.5`, `1000` should be `500` |
| Formula errors | Division instead of multiplication, wrong divisor |
| Logic inversion | `min` vs `max`, `any` vs `all`, negated conditions |
| Missing operations | Computation done but result unused |
| State machine errors | Wrong transitions, missing states in paths |
| Compensating bugs | Paired bugs that mask each other |
| Multi-file dependencies | Bugs requiring fixes across multiple modules |

## Getting Started

```bash
# Build and run all tests (use --no-fail-fast to run all binaries)
cargo test --no-fail-fast

# Run base tests only (skip matrix)
cargo test --no-fail-fast -- --skip hyper_matrix_scenarios

# Run matrix scenarios only
cargo test --test hyper_matrix -- --nocapture
```

## Constraints

- Do not modify files under `tests/`, `environment/`, or `Cargo.toml`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.

## Success Criteria

- All 12,755 tests pass (255 base + 12,500 matrix scenarios)
- Replay determinism preserved
- Security invariants enforced
- Policy escalation/deescalation correct

## Reward Function

The environment uses 10-tier sparse rewards (Apex):

```
Pass Rate → Reward
≥ 1.00 → 1.0
≥ 0.99 → 0.85
≥ 0.96 → 0.66
≥ 0.90 → 0.47
≥ 0.80 → 0.31
≥ 0.67 → 0.19
≥ 0.52 → 0.11
≥ 0.36 → 0.05
≥ 0.22 → 0.015
< 0.22 → 0.0
```

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Batch scheduler, workflow refactoring, statistics optimization, routing API, lock-free queue |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Model Registry, GPU Memory Allocator, Training Checkpoint Manager |

These tasks test different software engineering skills while using the same codebase.
