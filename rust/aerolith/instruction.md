# Aerolith - Autonomous Satellite Constellation Control Platform

**Language:** Rust
**Difficulty:** Ultra-Principal
**Bugs:** 153
**Tests:** 1362 (223 base + 1139 hyper-matrix scenarios)

## Overview

Fix bugs across an autonomous satellite constellation control platform. The codebase handles orbital correction planning, collision avoidance, downlink scheduling, anomaly triage, power management, and cross-station command synchronization.

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run tests
cargo test

# Run full verification
bash tests/test.sh
```

## Source Files

14 modules in `src/`:

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

## Bug Categories

| Category | Module(s) | Count |
|----------|-----------|-------|
| CFG | config.rs | 11 |
| ORB | orbit.rs | 14 |
| SAF | safety.rs | 14 |
| SEQ | sequencing.rs | 13 |
| ROU | routing.rs | 17 |
| SCH | scheduling.rs | 11 |
| POW | power.rs | 15 |
| TEL | telemetry.rs | 13 |
| RES | resilience.rs | 15 |
| AUT | auth.rs | 16 |
| EVT | events.rs | 6 |
| CON | concurrency.rs | 1 |
| INT | integration.rs | 7 |

## Bug Dependency Chains

Bugs form dependency chains — approximately 45% of bugs have prerequisites.
Chains range in depth from 2 to 6. Integration bugs depend on their upstream
module bugs being fixed first.

## Constraints

- Do **not** modify test files under `tests/`.
- All bugs are embedded in the source files.
- Each bug is a compilable logic error (wrong operator, wrong constant, inverted comparison, etc.).

## Success Criteria

All 1362 tests pass. Full-suite pass rate reaches 100%.

A submission is correct when Harbor writes reward `1.0`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Conjunction Screening, Telemetry Pipeline, Power Budget, Ground Station API, Circuit Breaker 2.0 |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Debris Avoidance Planner, Solar Panel Optimizer, Telemetry Compression |

These tasks test different software engineering skills while using the same codebase.
