# VectorHarbor - Hyper-Principal Maritime Orchestration Reliability Environment

VectorHarbor is a Rust 2021 maritime orchestration reliability platform that coordinates vessel allocation, route policy, replay safety, and security approvals under tight latency constraints.

The codebase contains issues across coupled modules with deep dependency chains.

## Architecture

| Module | File | Description |
| Allocator | `src/allocator.rs` | Dispatch planning, berth slot management, cost estimation, rolling window scheduler |
| Routing | `src/routing.rs` | Route selection, multi-leg planning, channel scoring, route table with RwLock |
| Policy | `src/policy.rs` | Operational mode state machine, escalation/de-escalation, SLA compliance tracking |
| Queue | `src/queue.rs` | Priority queue, rate limiter (token bucket), queue health metrics, shedding logic |
| Security | `src/security.rs` | Digest hashing, signature verification, HMAC manifest signing, token store, path sanitisation |
| Resilience | `src/resilience.rs` | Replay deduplication, checkpoint manager, circuit breaker state machine |
| Statistics | `src/statistics.rs` | Percentile calculation, descriptive stats, response time tracking, heatmap generation |
| Workflow | `src/workflow.rs` | State transition graph, BFS shortest path, workflow engine with entity lifecycle tracking |
| Models | `src/models.rs` | Dispatch orders, vessel manifests, severity classification, batch creation |
| Contracts | `src/contracts.rs` | Service definitions, URL resolution, contract validation, topological ordering |

## Difficulty

Hyper-Principal (70-140h expected).

## Objective

Fix production defects in source files under `src/`.

## Completion Criteria

- Full suite passes (`cargo test`) with **9200+ scenarios**.
- Deterministic replay and routing behavior is preserved.
- Security, workflow, and policy invariants remain enforced.
- Do not edit files under `tests/`.

## Getting Started

```bash
cargo test
```

## Infrastructure

- PostgreSQL 15 (port 5442) — dispatch orders, berth slots, vessel manifests, route channels
- Redis 7 (port 6402) — caching and rate limiting state

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that describe production symptoms without revealing solutions. Use these to practice investigative debugging:

| Scenario | Type | Description |
| `scenario_01_priority_dispatch.md` | Incident Report | High-priority vessels deprioritized, SLA breaches |
| `scenario_02_berth_scheduling.md` | Support Ticket | False conflict detection, incorrect wait estimates |
| `scenario_03_security_audit.md` | Security Alert | Path traversal incomplete, signature truncation |
| `scenario_04_policy_escalation.md` | Slack Discussion | Over-sensitive escalation, delayed de-escalation |
| `scenario_05_analytics_drift.md` | Dashboard Alert | Percentile drift, variance inflation, cost errors |

Each scenario describes observable symptoms and business impact. Your task is to correlate these symptoms with test failures and identify the underlying code defects.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | ANN indexing, similarity service refactoring, concurrent batch processing, metadata filtering, schema migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Vector compression service, index build orchestrator, query result ranker |

These tasks test different software engineering skills while using the same codebase.
