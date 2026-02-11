# ChronoMesh - Hyper-Principal Maritime Dispatch Reliability Environment

ChronoMesh is a C++20 maritime dispatch reliability platform that coordinates route dispatch, replay controls, queue pressure, and policy gating under tight latency constraints.

The codebase contains issues across coupled modules with deep dependency chains.

## Architecture

| Module | File | Description |
| Allocator | `src/allocator.cpp` | Dispatch planning, berth slot management, cost estimation, rolling window scheduler |
| Routing | `src/routing.cpp` | Route selection, multi-leg planning, channel scoring, route table with RW locks |
| Policy | `src/policy.cpp` | Operational mode state machine, escalation/de-escalation, SLA compliance tracking |
| Queue | `src/queue.cpp` | Priority queue, rate limiter (token bucket), queue health metrics, shedding logic |
| Security | `src/security.cpp` | Digest hashing, signature verification, HMAC manifest signing, token store, path sanitisation |
| Resilience | `src/resilience.cpp` | Replay deduplication, checkpoint manager, circuit breaker (closed/open/half-open) |
| Statistics | `src/statistics.cpp` | Percentile calculation, descriptive stats, response time tracker, heatmap generation |
| Workflow | `src/workflow.cpp` | State transition graph, BFS shortest path, workflow engine with entity lifecycle tracking |
| Models | `src/model.cpp` | Dispatch order model, vessel manifests, severity classification, batch creation |
| Contracts | `src/contracts.cpp` | Service definitions, URL resolution, contract validation, topological ordering |

## Difficulty

Hyper-Principal (70-140h expected).

## Objective

Fix production defects in source files under `src/` and `include/`.

## Completion Criteria

- Full suite passes (`cmake --build build && ctest --test-dir build --output-on-failure`) with **9200+ scenarios**.
- Deterministic replay and routing behavior is preserved.
- Security, workflow, and policy invariants remain enforced.
- Do not edit files under `tests/`.

## Getting Started

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
ctest --test-dir build --output-on-failure
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios based on production incidents:

| Scenario | Type | Areas Affected |
| `01_dispatch_priority_incident.md` | Incident Report | Allocator priority sorting, berth conflicts, cost estimation, capacity checks |
| `02_routing_cost_anomaly.md` | Analytics Alert | Channel scoring formula, route cost calculation, service URL resolution |
| `03_vessel_workflow_stuck.md` | Support Ticket | Workflow terminal states, state transitions, severity validation, urgency scoring |
| `04_security_bypass_postmortem.md` | Security Postmortem | Signature verification, path sanitization, replay ordering, checkpoint timing |
| `05_statistics_sla_drift.md` | Ops Alert + Slack | Percentile calculation, variance formula, policy escalation, queue shedding |

These scenarios describe **symptoms only** — the observable problems that operators, users, or monitoring systems would notice. Use them to understand the business impact of bugs and trace from symptoms to root causes.

## Infrastructure

- PostgreSQL 15 (port 5444) — dispatch orders, berth slots, vessel manifests, route channels
- Redis 7 (port 6404) — caching and rate limiting state

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Time-series aggregation, queue decoupling, route optimization, batch API, WAL migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Downsampling Engine, Retention Policy Enforcer, Anomaly Detection Pipeline |

These tasks test different software engineering skills while using the same codebase.
