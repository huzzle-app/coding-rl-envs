# IonVeil - Apex-Principal Planetary Emergency Command Platform

## Architecture

The platform consists of 10 microservices (gateway, auth, dispatch, routing, incidents, resources, notifications, analytics, audit, compliance) coordinating planetary emergency command, orbital relay routing, replay recovery, and cross-agency policy gates.

### Core Modules

| Module | Description |
|--------|-------------|
| `ionveil/models.py` | Domain models, severity classification, SLA tables |
| `ionveil/dispatch.py` | Dispatch planning, berth allocation, cost estimation |
| `ionveil/routing.py` | Route selection, channel scoring, multi-leg planning |
| `ionveil/policy.py` | Operational policy state machine, escalation/de-escalation |
| `ionveil/queue.py` | Priority queue, rate limiting, load shedding |
| `ionveil/security.py` | Signature verification, manifest signing, path sanitization |
| `ionveil/resilience.py` | Event replay, deduplication, circuit breaker |
| `ionveil/statistics.py` | Statistical aggregation, percentiles, moving average |
| `ionveil/workflow.py` | Entity lifecycle management, state transitions |

## Getting Started

```bash
python tests/run_all.py
```

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.

## Success Criteria

- All 12,tests pass
- Deterministic replay, scheduling, routing, and policy behavior remains stable
- Security, workflow, and compliance invariants remain enforced

## Reward Function

The environment uses 10-tier sparse rewards (Apex-Principal):

```
Pass Rate → Reward
< 10% → 0.00
10-22% → 0.015
22-36% → 0.05
36-52% → 0.11
52-67% → 0.19
67-80% → 0.31
80-90% → 0.47
90-96% → 0.66
96-99% → 0.85
100% → 1.00
```

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Cascading Policy Overrides, Queue Health Monitor, Batch Dispatch Planning, Route Failover, Event Sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Policy Simulator, Analytics Dashboard Backend, SLA Monitoring Service |

These tasks test different software engineering skills while using the same codebase.

Good luck!
