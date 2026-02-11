# IonVeil - Apex-Principal Planetary Emergency Command Environment

IonVeil coordinates planetary emergency command, orbital relay routing, replay recovery, and cross-agency policy gates.

The codebase contains issues spanning 15 categories with deep dependency chains across scheduling, replay, routing, policy, security, and infrastructure layers.

## Difficulty

Apex-Principal (5-7 days expected, 120-168h).

## Objective

Fix production defects in source files only.

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production issues. Each scenario describes symptoms and business context without revealing exact fixes:

| Scenario | Format | Description |
| `incident_001_replay_ordering.md` | Incident Report | Event replay returning stale state during DR testing |
| `incident_002_policy_escalation.md` | Incident Report | Policy engine fails to escalate during multi-failure event |
| `ticket_003_route_selection.md` | Support Ticket | Route selection choosing high-latency channels |
| `alert_004_config_precedence.md` | Monitoring Alert | Environment variables not overriding YAML config |
| `slack_005_dispatch_priority.md` | Team Discussion | Dispatch ordering producing unexpected sequences |

These scenarios provide entry points for investigation and reference failing tests that validate fixes.

## Completion Criteria

- Full suite passes (`python tests/run_all.py`) with **12,462+ scenarios**.
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Cascading Policy Overrides, Queue Health Monitor, Batch Dispatch Planning, Route Failover, Event Sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Policy Simulator, Analytics Dashboard Backend, SLA Monitoring Service |

These tasks test different software engineering skills while using the same codebase.
