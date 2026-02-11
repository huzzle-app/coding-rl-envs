# AtlasDispatch - Hyper-Principal Maritime Dispatch Reliability Environment

AtlasDispatch manages route allocation, replay controls, capacity pressure, and policy security gates.

The codebase contains issues across dense cross-module dependencies and concurrency-sensitive behavior.

## Difficulty

Hyper-Principal (70-140h expected).

## Objective

Fix production defects in source files only.

## Completion Criteria

- Full suite passes (`go test -race -v ./...`) with **9200+ scenarios**.
- Deterministic replay/routing behavior is preserved.
- Security, queue, and policy invariants remain enforced.
- Do not edit files under `tests/`.

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios based on production incidents. Each scenario describes symptoms without revealing solutions:

| Scenario | Type | Description |
| [01_urgent_cargo_delays.md](scenarios/01_urgent_cargo_delays.md) | Incident Report | Priority cargo being processed after low-urgency orders; SLA violations with premium partners |
| [02_route_selection_anomaly.md](scenarios/02_route_selection_anomaly.md) | Support Ticket | Route selection choosing highest-latency routes; inverted scoring causing fleet delays |
| [03_security_audit_findings.md](scenarios/03_security_audit_findings.md) | Security Alert | Penetration test findings including token validation, path traversal, and signature verification issues |
| [04_replay_divergence.md](scenarios/04_replay_divergence.md) | Slack Discussion | Event replay producing inconsistent state; checkpoint and circuit breaker anomalies |
| [05_workflow_stuck_orders.md](scenarios/05_workflow_stuck_orders.md) | PagerDuty Alert | Orders stuck in arrived state; missing state transitions and policy escalation issues |

These scenarios can guide your investigation by describing real symptoms observed in the system.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-carrier routing, queue refactoring, replay optimization, scheduling API, policy migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Proof of Delivery, Dynamic Rerouting, Driver Performance Tracker |

These tasks test different software engineering skills while using the same codebase.
