# Aerolith - Alternative Tasks

## Overview

The Aerolith satellite constellation control platform offers five alternative development tasks that test different software engineering capabilities: feature development for collision avoidance systems, refactoring telemetry pipelines, optimizing power budget calculations, extending ground station APIs, and migrating resilience frameworks. Each task builds on the existing codebase to add new functionality or improve existing subsystems.

## Environment

- **Language**: Rust
- **Infrastructure**: Docker-based development environment with full test suite (1220 tests)
- **Difficulty**: Ultra-Principal

## Tasks

### Task 1: Conjunction Screening Service Enhancement (Feature)

Implement a batch screening service for the collision avoidance system that evaluates multiple satellite-debris conjunction events in a single operation. This service must integrate with existing collision probability calculations, relative velocity computations, and avoidance window scheduling to produce prioritized lists of high-risk conjunctions with recommended maneuver windows and delta-v budgets.

Key requirements include configurable risk thresholds, filtering by satellite groups or orbital regimes, automatic high-priority scheduling slot reservation, and comprehensive summary statistics.

### Task 2: Telemetry Pipeline Consolidation (Refactoring)

Consolidate scattered health scoring, anomaly detection, and metric aggregation logic into a cohesive telemetry pipeline architecture. The refactoring establishes a clear flow from raw telemetry samples through anomaly detection, health scoring, and alerting decisions. This improves maintainability and enables easier addition of new sensor types while maintaining backward compatibility with existing health score calculations.

The refactored pipeline should use the builder pattern for configuration, support pluggable anomaly detectors, and ensure consistent jitter scoring across all sensor channels.

### Task 3: Power Budget Optimization for Eclipse Periods (Performance Optimization)

Optimize power budget calculations for multi-orbit eclipse sequences, improving accuracy and reducing unnecessary heater cycling. The system must correctly model eclipse fraction across consecutive orbits, account for panel degradation over mission lifetime, and maintain accurate depth-of-discharge tracking for battery health monitoring.

Focus on fixing eclipse drain calculations, solar panel output conversion, battery state-of-charge range enforcement, and charge time estimation accuracy.

### Task 4: Ground Station Network API Extension (API Extension)

Extend the mission operations API with comprehensive coverage for ground station network management, including real-time link margin monitoring, automatic handover sequencing, failover routing, and predictive contact scheduling with Doppler compensation. The API must integrate with antenna gain calculations and support multi-band frequency planning.

Ensure correct signal-to-noise polarity, proper free-space path loss calculations, inclusive visibility checks, and accurate Doppler shift sign handling.

### Task 5: Resilience Framework Migration to Circuit Breaker 2.0 (Migration)

Migrate the resilience framework from basic circuit breaker to an enhanced Circuit Breaker 2.0 specification with improved failure window detection, half-open state management, and cascade failure prevention. Update retry backoff strategy to true exponential growth, implement accurate failure window detection for time-bounded failure counting, and ensure proper half-open state behavior.

The migration must be backward compatible with existing resilience tests while enabling new monitoring capabilities.

## Getting Started

```bash
cargo test
```

Run this command to execute the full test suite. A successful implementation will pass all tests with no regressions to existing functionality.

## Success Criteria

Your implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md), which specifies detailed requirements for each task including acceptance criteria, integration points, and test expectations. All existing tests must continue to pass, and new functionality must integrate seamlessly with the existing codebase.
