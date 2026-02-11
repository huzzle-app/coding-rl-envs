# AetherOps - Hyper-Principal Orbital Operations Platform

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic behavior of scheduling and policy logic.
- Keep security checks (signature validation, path sanitization) intact.

## Success Criteria

- All 7,tests pass (`python tests/run_all.py`).
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.

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

Primary objective: make all tests pass with robust, production-safe fixes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Adaptive rate limiting, circuit breaker consolidation, telemetry optimization, GraphQL API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Incident Correlation Engine, Runbook Automation Service, Capacity Planning Predictor |

These tasks test different software engineering skills while using the same codebase.
