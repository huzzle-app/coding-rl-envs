# IronFleet - Apex-Principal Reliability Environment

IronFleet controls autonomous convoy mission planning, contested-network routing, replay convergence, and safety policy arbitration across a fleet of interconnected services.

The codebase contains deeply coupled service, data, resilience, and security defects with long dependency chains.

## Difficulty

Apex-Principal (5–7 days expected, 120–168h).

## Objective

Fix production defects in source files only. Do not modify files under `tests/`.

## Known Issues

Tests are failing in several areas. Previous maintainer noted problems with async operations and data handling.

## Test Breakdown

| Category | File | Tests |
|----------|------|-------|
| Unit | `tests/unit/core_test.go` | 8 |
| Integration | `tests/integration/flow_test.go` | 1 |
| Chaos | `tests/chaos/replay_test.go` | 2 |
| Contracts | `tests/services/contracts_test.go` | 1 |
| Service tests | `tests/services/*_service_test.go` | 32 |
| Hyper matrix | `tests/stress/hyper_matrix_test.go` | 7,001 |
| Service mesh matrix | `tests/stress/service_mesh_matrix_test.go` | 2,168 |
| Advanced bugs | `tests/stress/advanced_bugs_test.go` | 278 |
| **Total** | | **9,491** |

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that present bugs as they would appear in production:

| Scenario | Format | Domain Area |
|----------|--------|-------------|
| `incident_001_mission_prioritization.md` | Incident Report | Mission dispatch ordering failures |
| `incident_002_signature_verification.md` | Security Incident | Command authentication bypass |
| `ticket_003_convoy_routing.md` | Support Ticket | Suboptimal channel selection |
| `alert_004_fleet_health.md` | Prometheus Alert | Negative health metrics |
| `slack_005_replay_convergence.md` | Slack Discussion | Event replay data loss |

Each scenario describes symptoms, includes failing test references, and shows operational impact without revealing the fix.

## Completion Criteria

- Full suite passes (`go test -race -v ./...`)
- Deterministic replay, scheduling, routing, and policy behavior remains stable
- Security, workflow, and compliance invariants remain enforced
- Do not edit files under `tests/`

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Convoy tracking, route consolidation, queue optimization, telemetry API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Fuel Optimizer, Maintenance Scheduler, Geofence Alert Service |

These tasks test different software engineering skills while using the same codebase.
