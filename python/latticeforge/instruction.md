# LatticeForge - Apex-Principal Reliability Platform

## Architecture

The platform consists of 13 microservices orchestrating cross-market liquidity balancing, execution safety controls, deterministic replay, and risk-governance workflows.

### Core Modules

| Module | Description |
|--------|-------------|
| `latticeforge/models.py` | Domain models, severity classification |
| `latticeforge/policy.py` | Operational policy gates, escalation logic |
| `latticeforge/routing.py` | Route selection, channel scoring |
| `latticeforge/security.py` | Signature verification, manifest signing |
| `latticeforge/orbit.py` | Orbital relay calculations |
| `latticeforge/scheduler.py` | Task scheduling, deadline tracking |
| `latticeforge/queue.py` | Priority queue, rate limiting, load shedding |
| `latticeforge/resilience.py` | Event replay, deduplication, circuit breaker |
| `latticeforge/workflow.py` | Entity lifecycle, state transitions |
| `latticeforge/statistics.py` | Statistical aggregation, percentiles |
| `latticeforge/telemetry.py` | Metrics collection, trace propagation |
| `latticeforge/dependency.py` | Dependency resolution, topology ordering |

## Getting Started

```bash
python tests/run_all.py
```

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.

## Success Criteria

- All 15,tests pass
- Deterministic replay, scheduling, routing, and policy behavior remains stable
- Security, workflow, and compliance invariants remain enforced

## Reward Function

The environment uses 10-tier sparse rewards (Apex-Principal):

```
Pass Rate -> Reward
< 10% -> 0.00
10-22% -> 0.015
22-36% -> 0.05
36-52% -> 0.11
52-67% -> 0.19
67-80% -> 0.31
80-90% -> 0.47
90-96% -> 0.66
96-99% -> 0.85
100% -> 1.00
```

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Health-aware routing, circuit breaker extraction, batch optimization, rate limiting, policy engine |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Service Discovery Registry, Traffic Mirroring Service, Distributed Tracing Collector |

These tasks test different software engineering skills while using the same codebase.

Good luck!
