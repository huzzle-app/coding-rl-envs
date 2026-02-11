# HeliosOps - Alternative Tasks

## Overview

Five alternative engineering tasks for the HeliosOps satellite operations platform, each simulating different real-world development scenarios: feature development, refactoring, performance optimization, API extension, and system migration.

## Environment

- **Language**: Python
- **Infrastructure**: PostgreSQL x3, Redis, NATS
- **Difficulty**: Hyper-Principal

## Tasks

### Task 1: Orbital Conjunction Alert System (Feature)

Implement an automated conjunction detection system that identifies close approaches between tracked satellites, calculates predicted trajectories, and generates prioritized alerts. The system must integrate with existing geospatial and routing modules, handle 10,000+ tracked objects, and provide operators with time-to-conjunction, miss distance estimates, and maneuver window recommendations.

### Task 2: Ground Station Contact Window Consolidation (Refactoring)

Consolidate fragmented contact window calculations scattered across geo, scheduler, and routing modules into a unified service. Eliminate code duplication, apply consistent atmospheric refraction corrections, and maintain backward compatibility while fixing discrepancies in pass predictions for polar-orbiting satellites.

### Task 3: Telemetry Downlink Throughput Optimization (Performance)

Optimize the telemetry processing pipeline to sustain 50,000 events/second during burst periods. Replace naive O(n) deduplication with O(1) amortized lookups, implement incremental projection updates, and tune the circuit breaker for burst tolerance without compromising fault detection.

### Task 4: Spacecraft Command Authorization API (API Extension)

Extend the security module with a command authorization workflow that validates operator credentials, checks spacecraft command syntax, detects conflicts, and enforces dual-control approval for critical operations. Support both synchronous and asynchronous command queuing with comprehensive audit logging.

### Task 5: Legacy TLE to Ephemeris Format Migration (Migration)

Migrate from Two-Line Element (TLE) orbital state representation to ephemeris-based state vectors with covariance data. Support dual-format operation during transition, implement automatic format detection, use appropriate propagation models (SGP4 vs. numerical integration), and provide data quality indicators.

## Getting Started

```bash
python tests/run_all.py
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
