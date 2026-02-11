# HeliosOps - Hyper-Principal Orbital Response Reliability Platform

## Architecture

The platform consists of 12 microservices coordinating mission dispatch, orbital relay routing, replay recovery, and cross-agency policy gates.

### Core Modules

| Module | Description |
|--------|-------------|
| `heliosops/models.py` | Domain models, severity classification, SLA tables |
| `heliosops/dispatch.py` | Dispatch planning, berth allocation, cost estimation |
| `heliosops/geo.py` | Geospatial calculations, coordinate transforms |
| `heliosops/routing.py` | Route selection, channel scoring, multi-leg planning |
| `heliosops/policy.py` | Operational policy state machine, escalation/de-escalation |
| `heliosops/queue.py` | Priority queue, rate limiting, load shedding |
| `heliosops/security.py` | Signature verification, manifest signing, path sanitization |
| `heliosops/resilience.py` | Event replay, deduplication, circuit breaker |
| `heliosops/scheduler.py` | Task scheduling, cron management, deadline tracking |
| `heliosops/statistics.py` | Statistical aggregation, percentiles, moving average |
| `heliosops/workflow.py` | Entity lifecycle management, state transitions |

## Getting Started

```bash
python tests/run_all.py
```

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks and policy gates intact.

## Success Criteria

- All 9,tests pass
- Routing, queue, policy, and replay behavior remain deterministic
- Security and workflow invariants remain enforced

## Reward Function

The environment uses 8-tier sparse rewards (Hyper-Principal):

```
Pass Rate -> Reward
< 25% -> 0.00
25-40% -> 0.05
40-55% -> 0.12
55-70% -> 0.22
70-85% -> 0.38
85-95% -> 0.55
95-100% -> 0.78
100% -> 1.00
```

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Conjunction alert system, contact window consolidation, telemetry optimization, command auth API, TLE migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Constellation Coordinator, Health Monitor, Ground Station Scheduler |

These tasks test different software engineering skills while using the same codebase.

Good luck!
