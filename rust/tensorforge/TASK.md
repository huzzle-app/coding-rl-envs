# TensorForge - Apex-Principal Reliability Environment

TensorForge is a Rust-based realtime model-serving exchange control platform with replay determinism, risk policy coupling, and secure orchestration flows. The system manages dispatch order allocation, multi-leg routing, policy escalation/deescalation, circuit breaker resilience, event ordering, telemetry collection, and workflow state machines across 13 services.

The codebase contains **1270 deeply interconnected bugs** spanning 10 categories — from configuration defaults and concurrency primitives to security validation and data integrity. Bugs have long dependency chains (depth 3-8) with chained and diamond prerequisites across policy, routing, replay, and security flows.

## Difficulty

Apex-Principal (5-7 days expected, 120-168 hours).

## Objective

Fix production defects in source files only. All bugs are compilable logic errors — wrong operators, inverted comparisons, missing operations, off-by-one boundaries, wrong formulas, and unused computations.

## Architecture

### Source Modules (14 files)

| Module | Focus | Lines |
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

### Services (13 microservices)

| Service | Port | Dependencies |
| gateway | 8120 | — |
| routing | 8121 | gateway |
| policy | 8122 | gateway |
| resilience | 8123 | gateway |
| analytics | 8124 | gateway, routing |
| audit | 8125 | gateway |
| notifications | 8126 | gateway, audit |
| security | 8127 | gateway |
| intake | — | gateway |
| identity | — | gateway |
| fulfillment | — | gateway |
| reporting | — | gateway |

## Infrastructure

- **PostgreSQL 15** on port 5442
- **Redis 7** on port 6402
- Docker Compose for service orchestration

## Getting Started

```bash
# Build and run all tests
cargo test

# Run base tests only (skip matrix)
cargo test -- --skip hyper_matrix_scenarios

# Run matrix scenarios only
cargo test --test hyper_matrix -- --nocapture
```

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that present production issues as they would appear in real-world operations:

| Scenario | Type | Primary Module | Description |
| `incident_001_inference_latency_misrouting.md` | Incident Report | routing | Inference requests routed to highest-latency endpoints instead of lowest |
| `incident_002_authentication_bypass.md` | Incident Report | security | Empty authentication tokens accepted, bypassing security layer |
| `ticket_003_allocation_cost_explosion.md` | Support Ticket | allocator | Cost estimates returning 1000x expected values |
| `alert_004_telemetry_health_scoring.md` | Monitoring Alert | telemetry | False positive health alerts due to inverted metric calculations |
| `slack_005_event_ordering_replay.md` | Team Discussion | events, resilience | Events returned in reverse order, replay determinism broken |

Each scenario describes **symptoms only** - observable behavior, business impact, failing tests, and investigation clues. The scenarios do not reveal exact bug locations or fixes.

Use these scenarios to:
- Practice real-world debugging workflows
- Understand how bugs manifest in production systems
- Learn to trace symptoms back to root causes
- Experience the interconnected nature of bugs in complex systems

## Completion Criteria

- Full suite passes (`cargo test`) with **12,685 scenarios**.
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Batch scheduler, workflow refactoring, statistics optimization, routing API, lock-free queue |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Model Registry, GPU Memory Allocator, Training Checkpoint Manager |

These tasks test different software engineering skills while using the same codebase.
