# VertexGrid - Apex-Principal Reliability Environment

VertexGrid operates continental balancing and dispatch optimization with failure replay control, policy safeguards, and audit-critical decisioning.

The environment contains issues across deep dependency chains:
- **82 handcrafted core bugs** across Spring, concurrency, persistence, and security.
- **1168 expanded apex bugs** mapped onto production-style test names.
- **12,000+ stress scenarios** in hyper-matrix execution.

## Difficulty

Apex-Principal (5-7 days expected, 120-168h).

## Objective

Fix production defects in source files only.

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that describe production issues without revealing solutions:

| Scenario | Format | Description |
| `incident_001_dispatch_deadlock.md` | Incident Report | ForkJoinPool thread starvation during peak dispatch operations |
| `incident_002_billing_precision.md` | Incident Report | Revenue discrepancies and geographic billing zone mismatches |
| `ticket_003_notification_failures.md` | Support Ticket | Cache collisions, delivery slowdowns, and visibility issues |
| `alert_004_concurrent_modification.md` | Monitoring Alert | ConcurrentModificationException in dispatch listeners |
| `slack_005_analytics_issues.md` | Team Discussion | CSV performance, pagination, caching, and tracing issues |

Each scenario includes:
- Detailed symptom descriptions
- Business impact assessment
- Relevant log snippets and metrics
- List of affected test cases
- Investigation hints (without solutions)

Use these scenarios to understand how bugs manifest in production and to guide your debugging approach.

## Completion Criteria

- Full suite passes (`mvn -q test`) including 12,000+ stress cases.
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Geofencing alerts, monetary refactoring, pipeline optimization, REST API v2, dispatch migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Energy Consumption Analyzer, Demand Response Coordinator, Carbon Footprint Calculator |

These tasks test different software engineering skills while using the same codebase.
