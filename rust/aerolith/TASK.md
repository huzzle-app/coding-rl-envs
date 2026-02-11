# Aerolith — Autonomous Satellite Constellation Control Platform

You are debugging a **Rust** platform that coordinates autonomous satellite clusters:
orbital correction planning, collision avoidance, downlink scheduling, anomaly triage,
power management, and cross-station command synchronization.

| Property | Value |
|----------|-------|
| Language | Rust |
| Difficulty | Ultra-Principal |
| Tests | 1362 (223 base + 1139 hyper-matrix scenarios) |

## Architecture

14 source modules in `src/`:

| Module | Area |
|--------|------|
| config.rs | Defaults, validation, feature flags |
| orbit.rs | Orbital mechanics, period, velocity |
| safety.rs | Collision risk, debris, keep-out zones |
| sequencing.rs | Command priority, dedup, batching |
| routing.rs | Link budget, ground station, antenna |
| scheduling.rs | Contact windows, eclipse, overlap |
| power.rs | Solar, battery, power budget |
| telemetry.rs | Metrics, alerting, health scoring |
| resilience.rs | Retry, circuit breaker, bulkhead |
| auth.rs | Token, permissions, rate limiting |
| events.rs | Event sorting, dedup, filtering |
| concurrency.rs | Thread-safe state, priority queues, rate limiters |
| integration.rs | Cross-module pipelines (conjunction, downlink, orbit) |
| planner.rs | Burn plan validation (bug-free) |

## Bug Dependency Chains

Bugs form dependency chains — some bugs block others. Approximately 45% of bugs have
prerequisites. Chains range in depth from 2 to 6.

## Getting Started

```bash
docker compose up -d # start infrastructure
cargo test # run all tests
```

## Constraints

- Do **not** modify test files under `tests/`.
- All bugs are embedded in the source codes in source files.
- Each bug is a compilable logic error (wrong operator, wrong constant, inverted comparison, etc.).

## Success Criteria

All 1362 tests pass. Full-suite pass rate reaches 100%.

## Reward Function (8-tier)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.0 |
| >= 0.95 | 0.78 |
| >= 0.85 | 0.55 |
| >= 0.70 | 0.38 |
| >= 0.55 | 0.22 |
| >= 0.40 | 0.12 |
| >= 0.25 | 0.05 |
| < 0.25 | 0.0 |

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that describe production symptoms without revealing solutions:

| Scenario | Type | Domain | Severity |
| [01_orbital_anomaly.md](scenarios/01_orbital_anomaly.md) | Incident Report | Orbital Mechanics, Power | P1 |
| [02_ground_station_outage.md](scenarios/02_ground_station_outage.md) | On-Call Alert | Communication, Routing | P2 |
| [03_collision_avoidance.md](scenarios/03_collision_avoidance.md) | Mission Report | Safety, Scheduling | P1 |
| [04_telemetry_drift.md](scenarios/04_telemetry_drift.md) | Slack Thread | Telemetry, Resilience | P3 |
| [05_auth_bypass.md](scenarios/05_auth_bypass.md) | Security Ticket | Auth, Config | P1 |

Each scenario covers multiple interconnected bugs across different modules. Use these as entry points for investigation.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Conjunction Screening, Telemetry Pipeline, Power Budget, Ground Station API, Circuit Breaker 2.0 |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Debris Avoidance Planner, Solar Panel Optimizer, Telemetry Compression |

These tasks test different software engineering skills while using the same codebase.
