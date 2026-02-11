# LatticeForge - Apex-Principal Reliability Environment

LatticeForge orchestrates cross-market liquidity balancing, execution safety controls, deterministic replay, and risk-governance workflows.

The codebase contains issues across deeply coupled service, data, resilience, and security defects across long dependency chains.

## Difficulty

Apex-Principal (5-7 days expected, 120-168h).

## Objective

Fix production defects in source files only.

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging context - incident reports, support tickets, alerts, and team discussions that describe symptoms without revealing fixes:

| Scenario | Type | Key Symptoms |
| `incident_001_high_latency.md` | Incident | Ground station routing picks high-latency paths |
| `incident_002_missed_alerts.md` | Incident | Critical alerts only trigger email, not pager/SMS |
| `ticket_003_reports_wrong_order.md` | Ticket | Reports list low-severity issues before critical |
| `alert_004_gateway_degraded.md` | Alert | Gateway routes to degraded nodes |
| `slack_005_failover_issue.md` | Slack | Failover selects degraded regions |

Use these to understand real-world impact and guide investigation.

## Completion Criteria

- Full suite passes (`python tests/run_all.py`) with **15,270 scenarios**.
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Health-aware routing, circuit breaker extraction, batch optimization, rate limiting, policy engine |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Service Discovery Registry, Traffic Mirroring Service, Distributed Tracing Collector |

These tasks test different software engineering skills while using the same codebase.
