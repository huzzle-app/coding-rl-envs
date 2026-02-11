# OpalCommand - Apex-Principal Reliability Environment

OpalCommand runs catastrophe claims command workflows with queue pressure control, settlement replay safety, and security policy enforcement. The codebase contains deeply coupled service, data, resilience, and security defects with long dependency chains.

## Difficulty

Apex-Principal (5-7 days expected, 120-168h).

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that describe production issues without revealing solutions:

| Scenario | Type | Focus Areas |
| `incident_001_settlement_replay_corruption.md` | P1 Incident | Event replay selecting wrong sequences, deduplication gaps, checkpoint intervals |
| `incident_002_routing_cost_overruns.md` | P2 Incident | Corridor selection inverted, wrong default constants, distance calculation errors |
| `ticket_003_priority_queue_mishandling.md` | Support Ticket | Priority sort direction, queue thresholds, partition boundaries |
| `alert_004_security_audit_failures.md` | Security Alert | Session/token boundaries, path traversal encoding, audit validation gaps |
| `slack_005_analytics_dashboard_issues.md` | Team Discussion | Ranking inversions, statistical formulas, threshold boundaries, inactive filtering |

Each scenario describes symptoms, business impact, and failing tests to guide investigation. Use these as realistic starting points for debugging sessions.

## Completion Criteria

- Full suite passes: `ruby -Ilib -Itests tests/run_all.rb`
- **9,263+ tests** pass deterministically
- Replay, scheduling, routing, and policy behavior remains stable
- Security, workflow, and compliance invariants remain enforced
- Do **not** edit files under `tests/`

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Command batching, corridor indexing, settlement caching, workflow API, event store migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Berth Optimizer, Cargo Manifest Validator, Vessel Tracking Service |

These tasks test different software engineering skills while using the same codebase.
