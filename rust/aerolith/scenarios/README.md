# Aerolith Debugging Scenarios

This directory contains 5 realistic debugging scenarios for the Aerolith satellite constellation control platform. Each scenario describes symptoms observed in production without revealing the underlying cause.

## Scenarios Overview

| File | Type | Domain | Severity |
|------|------|--------|----------|
| 01_orbital_anomaly.md | Incident Report | Orbital Mechanics / Power | P1 - Critical |
| 02_ground_station_outage.md | On-Call Alert | Communication / Routing | P2 - High |
| 03_collision_avoidance.md | Mission Report | Safety / Scheduling | P1 - Critical |
| 04_telemetry_drift.md | Slack Thread | Telemetry / Resilience | P3 - Medium |
| 05_auth_bypass.md | Security Ticket | Auth / Config | P1 - Critical |

## How to Use

1. Read the scenario to understand the symptoms
2. Investigate the codebase to identify root causes
3. Fix the underlying bugs in the source modules
4. Run `cargo test` to verify your fixes

## Scenario Categories

Each scenario involves multiple interconnected bugs across different modules:

- **Orbital Mechanics** (orbit.rs): Period calculation, transfer orbits, velocity
- **Power Management** (power.rs): Solar output, battery, eclipse drain
- **Safety/Collision** (safety.rs): Risk assessment, keep-out zones, debris
- **Communication** (routing.rs): Link budget, antenna gain, ground stations
- **Scheduling** (scheduling.rs): Contact windows, eclipse timing, overlap
- **Telemetry** (telemetry.rs): Metrics, alerts, health scoring
- **Resilience** (resilience.rs): Circuit breakers, retry logic, failover
- **Auth** (auth.rs): Tokens, permissions, rate limiting
- **Config** (config.rs): Defaults, validation, feature flags

## Notes

- Scenarios are interconnected; fixing one may reveal issues in another
- Some bugs have dependency chains requiring fixes in a specific order
- Do not modify test files - only fix bugs in `src/` modules
