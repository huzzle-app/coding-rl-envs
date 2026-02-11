Fix production defects in ObsidianMesh by editing source code only.

ObsidianMesh is an Apex-Principal C++ environment with issues and tests (178 base + 12500 hyper-matrix). It implements deterministic replay correction, constrained routing, safety-policy gates, and real-time telemetry across 14 source modules and 13 microservices.

## Reward Thresholds (10-tier Apex)

```
>=1.0 → 1.0 | >=0.99 → 0.85 | >=0.96 → 0.66 | >=0.90 → 0.47
>=0.80 → 0.31 | >=0.67 → 0.19 | >=0.52 → 0.11 | >=0.36 → 0.05
>=0.22 → 0.015 | else → 0.0
```

## Constraints

- Do not modify files under `tests/`
- Preserve deterministic replay and scheduling behavior
- Keep security checks, policy gates, and audit invariants intact
- All bugs are compilable logic errors (wrong operators, formulas, constants)

## Getting Started

```bash
cmake -B build && cmake --build build
ctest --test-dir build --output-on-failure
```

Primary objective: make the full suite pass (`ctest --output-on-failure`) with production-safe changes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-zone partitioning, queue management refactoring, routing optimization, event streaming, time-series migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Topology optimizer, health monitor, traffic shaper |

These tasks test different software engineering skills while using the same codebase.
