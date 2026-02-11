Fix production defects in IronFleet by editing source code only.

IronFleet is an Apex-Principal Go environment and **tests** covering allocation/routing correctness, replay recovery, policy-security invariants, and cross-service integration.

## Architecture

| Layer | Path | Description |

## Known Issues

Tests are failing in several areas. Previous maintainer noted problems with async operations and data handling.

|-------|------|-------------|
| Core modules | `internal/*/` | 8 modules: allocator, routing, resilience, policy, queue, security, statistics, workflow |
| Models | `pkg/models/` | DispatchOrder, VesselManifest, severity constants |
| Services | `services/*/` | 8 service modules: gateway, audit, analytics, notifications, policy, resilience, routing, security |
| Contracts | `shared/contracts/` | Service definitions, topological ordering, URL resolution |

## Getting Started

```bash
go test -race -v ./...
```

No Docker or external services required.

## Test Breakdown

| Category | Count |
|----------|-------|
| Unit tests (core_test.go) | 8 |
| Integration (flow_test.go) | 1 |
| Chaos (replay_test.go) | 2 |
| Contract test | 1 |
| Service tests (8 files x 4) | 32 |
| Hyper matrix (subtests) | 7,001 |
| Service mesh matrix (subtests) | 2,168 |
| **Total** | **9,213** |

## Reward Tiers (10-threshold, Apex)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.0 |
| >= 0.99 | 0.85 |
| >= 0.96 | 0.66 |
| >= 0.90 | 0.47 |
| >= 0.80 | 0.31 |
| >= 0.67 | 0.19 |
| >= 0.52 | 0.11 |
| >= 0.36 | 0.05 |
| >= 0.22 | 0.015 |
| < 0.22 | 0.0 |

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.
- All changes must be production-safe.

Primary objective: make the full suite pass (`go test -race -v ./...`) with production-safe changes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Convoy tracking, route consolidation, queue optimization, telemetry API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Fuel Optimizer, Maintenance Scheduler, Geofence Alert Service |

These tasks test different software engineering skills while using the same codebase.
