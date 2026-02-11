# AetherOps - Hyper-Principal Orbital Operations Environment

AetherOps orchestrates orbital burns, mission risk controls, telemetry anomaly handling, replay resilience, and service-level compliance across 13 microservices.

The codebase contains issues spanning 13 categories with deep dependency chains across scheduling, replay, routing, policy, security, and infrastructure layers.

## Difficulty

Hyper-Principal (3-5 days expected, 70-140h).

## Objective

Fix production defects in source files only.

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that simulate production incidents, support tickets, and team discussions. These scenarios describe symptoms and business impact without revealing exact fixes.

| # | Scenario | Format | Module |
| 01 | Suboptimal Burn Window Selection | Incident Report | orbit.py |
| 02 | Circuit Breaker Fails to Trip | Slack Thread | resilience.py |
| 03 | Critical Alerts Missing Pager | Jira Ticket | notifications/service.py |
| 04 | SLA Calculation 10x Too Low | PagerDuty Alert | policy.py |
| 05 | Queue Priority Inversion | Post-Mortem | queue.py |

Use these scenarios to practice real-world debugging workflows. Each scenario references specific failing tests to guide investigation.

## Completion Criteria

- Full suite passes (`python tests/run_all.py`) with **7,150+ scenarios**.
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Adaptive rate limiting, circuit breaker consolidation, telemetry optimization, GraphQL API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Incident Correlation Engine, Runbook Automation Service, Capacity Planning Predictor |

These tasks test different software engineering skills while using the same codebase.
