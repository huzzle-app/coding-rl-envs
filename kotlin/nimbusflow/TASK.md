# NimbusFlow - Hyper-Principal Maritime Dispatch Reliability Environment

NimbusFlow coordinates dispatch planning, replay resilience, route policy, and security controls for maritime operations. The platform manages vessel berth allocation, multi-leg route planning, policy escalation/de-escalation, circuit breaker resilience, and real-time workflow tracking across eight interconnected services.

The codebase contains 25 bugs across deep cross-module dependencies and deterministic invariants.

## Difficulty

Hyper-Principal (70-140h expected).

## Infrastructure

- **PostgreSQL 15**: Primary persistence for orders, routes, manifests, checkpoints
- **Redis 7**: Token store, rate limiter state, queue overflow buffer

## Objective

Fix production defects in source files only.

## Completion Criteria

- Full suite passes (`mvn test`) with **9316 scenarios**.
- Deterministic replay/routing behavior is preserved.
- Security and workflow invariants remain enforced.
- Do not edit files under `src/test/`.

## Getting Started

```bash
cd kotlin/nimbusflow && mvn test
```

## Bug Categories

| Category | Count | Description |
|----------|-------|-------------|
| Logic inversion | 5 | Wrong comparison direction, inverted conditions |
| Wrong operator | 5 | Multiplication vs division, addition vs subtraction |
| Off-by-one | 3 | Boundary conditions using `<` vs `<=`, `>` vs `>=` |
| Wrong constant | 2 | Incorrect ratio, wrong formula coefficient |
| Missing feature | 3 | Missing keywords, missing port, missing terminal state |
| Missing guard | 4 | Unconditional history write, negative coord handling, race conditions (x2) |
| Wrong formula | 2 | Percentile rank calculation, floor vs ceil |
| Wrong graph edge | 1 | Invalid state transition in workflow |

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios based on production incidents. Each scenario describes symptoms without revealing the root cause:

| Scenario | Type | Description |
| `001_tanker_priority_incident.md` | PagerDuty Incident | Critical tankers delayed while low-priority vessels allocated first |
| `002_route_cost_anomaly.md` | Finance Audit | Route costs consistently underestimated; channel scoring favors high-latency routes |
| `003_policy_escalation_chaos.md` | Slack Thread | Policy engine escalates on single failures, de-escalates too quickly |
| `004_security_path_traversal.md` | Security Alert | Path sanitization bypassed using Windows-style backslash separators |
| `005_replay_state_divergence.md` | Ops Postmortem | Event replay keeps oldest events instead of latest; checkpoint intervals off-by-one |

These scenarios provide realistic context for debugging without spoiling the investigation. Use them to practice root cause analysis.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Checkpoint recovery, unified rate limiting, route caching, priority overrides, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Workflow Debugger Service, Cost Attribution Engine, Deployment Rollback Manager |

These tasks test different software engineering skills while using the same codebase.
