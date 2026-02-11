# SignalDock - Hyper-Principal Maritime Dispatch Reliability Environment

SignalDock coordinates berth allocation, route recovery, replay convergence, and policy/security enforcement under outage pressure.

The codebase contains issues across coupled routing, replay, policy, and queue subsystems with deep dependency chains.

## Difficulty

Hyper-Principal (70-140h expected).

## Objective

Restore production-safe behavior by fixing defects in source code only.

## Completion Criteria

- Full suite passes (`npm test`) with **9200+ scenarios**.
- Deterministic replay, scheduling, and routing behavior is preserved.
- Security, workflow, and policy invariants remain intact.
- Do not modify files under `tests/`.

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that simulate how these bugs might manifest in production:

| Scenario | Type | Description |
| [001](scenarios/001_vessel_scheduling_reversed.md) | Incident Report | Emergency vessels deprioritized in berth allocation |
| [002](scenarios/002_circuit_breaker_stuck_open.md) | Slack Thread | Circuit breaker never allows recovery after failures |
| [003](scenarios/003_replay_convergence_failures.md) | Post-Incident Review | Event replay produces inconsistent state across sites |
| [004](scenarios/004_security_origin_bypass.md) | Security Alert | Missing origin headers bypass access control |
| [005](scenarios/005_metrics_dashboard_wrong_numbers.md) | Support Ticket | Dashboard metrics consistently off by incorrect values |

These scenarios describe **symptoms only** - the business impact and observed behavior without revealing the underlying bugs. Use them to practice realistic debugging workflows.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Zone aggregation, Policy DSL, Circuit breaker optimization, Manifest API, Replay storage |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | AIS Signal Decoder, Port Congestion Monitor, Vessel ETA Predictor |

These tasks test different software engineering skills while using the same codebase.
