# StrataGuard - Apex-Principal Reliability Environment

StrataGuard is a C# reliability platform handling defense cyber incident command with deterministic workflow replay, queue backpressure safety, and hardened authorization paths.

The codebase contains deeply coupled service, data, resilience, and security defects with long dependency chains across 10 source modules.

## Difficulty

Apex-Principal (5–7 days expected, 120–168h).

## Getting Started

```bash
dotnet test --verbosity normal
```

Review the test output to understand which assertions fail, then trace failures back to source code defects.

## Constraints

- **Do not modify files under `tests/`.**
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.
- Only edit files under `src/StrataGuard/`.

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios to help you understand bugs in business context:

| Scenario | Type | Description |
| `incident_001_dispatch_priority_inversion.md` | Incident Report | Critical dispatch orders processed behind low-priority ones |
| `incident_002_replay_sequence_corruption.md` | Incident Report | Replay engine keeps wrong sequence during failover recovery |
| `ticket_003_route_selection_latency.md` | Support Ticket | Customer reports routes selected by highest latency |
| `alert_004_queue_drain_overflow.md` | Monitoring Alert | DrainBatch returns batchSize+1 items causing memory pressure |
| `slack_005_statistics_integer_division.md` | Team Discussion | Multiple metrics returning 0 instead of decimal values |

Each scenario describes **symptoms and failing tests** without revealing exact fixes. Use them to:
- Understand the business impact of bugs
- Practice realistic debugging workflows
- Learn the codebase through investigation

## Completion Criteria

- Full suite passes (`dotnet test`).
- All 9281 tests pass with zero failures.
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-Tier Queue, Policy State Machine, Route Optimization, Checkpoint API, Distributed Cache |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Intrusion Detection Service, Compliance Audit Logger, Security Policy Evaluator |

These tasks test different software engineering skills while using the same codebase.
