# OpalCommand — Apex-Principal Ruby Debugging Environment

Fix 1,240 production defects across 9 core modules, 12 service modules, and shared contracts in a Ruby reliability platform.

## Architecture

OpalCommand is a maritime operations command platform with three layers:

- **Core** (`lib/opalcommand/core/`): 9 modules — order, dispatch, policy, queue, resilience, routing, security, statistics, workflow
- **Services** (`services/*/service.rb`): 12 domain services — gateway, auth, intake, ledger, settlement, reconcile, policy, risk, audit, analytics, notifications, reporting
- **Contracts** (`shared/contracts/contracts.rb`): Service registry with 14 definitions, topological ordering, URL resolution

Bugs are embedded in the source codes in source files. Common categories:
- Comparison operators (`>` vs `>=`, sort direction)
- Wrong coefficients and formula errors
- Missing validation checks
- Ignored parameters and logic gaps
- Security issues (missing URL decode, case sensitivity)

## Getting Started

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Test Breakdown

| Category | Count |
|----------|-------|
| Unit tests | 60 |
| Integration tests | 3 |
| Service tests | 49 |
| Stress: hyper_matrix | 7,000 |
| Stress: service_mesh_matrix | 2,152 |
| **Total** | **9,263+** |

## Reward Tiers (10-threshold Apex)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.00 |
| >= 0.99 | 0.85 |
| >= 0.96 | 0.66 |
| >= 0.90 | 0.47 |
| >= 0.80 | 0.31 |
| >= 0.67 | 0.19 |
| >= 0.52 | 0.11 |
| >= 0.36 | 0.05 |
| >= 0.22 | 0.015 |
| >= 0.10 | 0.0 |

## Constraints

- Do **not** modify files under `tests/`
- Preserve deterministic replay and scheduling behavior
- Keep security checks, policy gates, and audit invariants intact
- Fix source code only: `lib/`, `services/`, `shared/`

## Objective

Make the full test suite pass deterministically with production-safe changes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Command batching, corridor indexing, settlement caching, workflow API, event store migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Berth Optimizer, Cargo Manifest Validator, Vessel Tracking Service |

These tasks test different software engineering skills while using the same codebase.
