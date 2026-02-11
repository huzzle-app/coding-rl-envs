# Aerolith - Alternative Task Specifications

This document describes alternative development tasks for the Aerolith satellite operations platform. Each task represents a realistic engineering scenario that could arise during platform development and maintenance.

---

## Task 1: Conjunction Screening Service Enhancement (Feature Development)

### Description

The current collision avoidance system processes conjunctions individually, but mission control has requested a batch screening service that can evaluate multiple satellite-debris conjunction events in a single operation. This is critical for constellation operations where hundreds of satellites may need collision risk assessment during a debris cloud transit.

The new screening service must integrate with the existing `safety.rs` collision probability calculations, `orbit.rs` relative velocity computations, and `scheduling.rs` avoidance window scheduling. The service should produce a prioritized list of conjunctions requiring immediate attention, along with recommended avoidance maneuver windows for each high-risk event.

The feature must support configurable risk thresholds, allow filtering by satellite groups or orbital regimes, and provide estimated delta-v budgets for proposed avoidance maneuvers using Hohmann transfer calculations.

### Acceptance Criteria

- Batch conjunction screening accepts a list of satellite-object pairs with TCA (Time of Closest Approach) and miss distance predictions
- Each conjunction is scored using collision probability calculations with cross-section and distance parameters
- Results are sorted by threat level (descending) with ties broken by TCA (ascending)
- Avoidance windows are computed using the collision avoidance window function with configurable lead times
- Delta-v estimates for avoidance burns are provided using the Hohmann transfer and inclination change functions
- High-priority conjunctions (threat level >= 3) trigger automatic scheduling slot reservation
- Service returns summary statistics including total conjunctions screened, by-threat-level counts, and total delta-v budget
- All existing collision avoidance and orbital mechanics tests continue to pass

### Test Command

```bash
cargo test
```

---

## Task 2: Telemetry Pipeline Consolidation (Refactoring)

### Description

The telemetry subsystem has grown organically over multiple releases, resulting in scattered health scoring, anomaly detection, and metric aggregation logic. The current architecture has metric formatting in `telemetry.rs`, threshold checking duplicated across modules, and inconsistent staleness detection patterns.

This refactoring task consolidates all telemetry processing into a cohesive pipeline architecture. The goal is to establish a clear flow from raw telemetry samples through anomaly detection, health scoring, and finally to alerting decisions. This will improve maintainability and make it easier to add new sensor types in future releases.

The refactored pipeline should use the builder pattern for configuration, support pluggable anomaly detectors, and provide consistent jitter scoring across all sensor channels. Backward compatibility with existing health score calculations must be maintained.

### Acceptance Criteria

- Create a unified TelemetryPipeline struct that orchestrates sample processing
- Extract common threshold checking logic into reusable predicate functions
- Consolidate staleness detection to use a single canonical implementation
- Implement consistent jitter scoring using absolute difference for all sensor types
- Metric formatting follows a single pattern with configurable separators and unit annotations
- Alert conditions are evaluated uniformly using the should_alert pattern
- Error rate and throughput calculations use consistent formulas across the codebase
- Latency bucketing boundaries are documented and applied consistently
- All existing telemetry and observability tests continue to pass

### Test Command

```bash
cargo test
```

---

## Task 3: Power Budget Optimization for Eclipse Periods (Performance Optimization)

### Description

Satellite operations during eclipse periods are currently experiencing power budget miscalculations that lead to conservative battery reserves. The power management system computes eclipse drain, solar panel output, and battery state-of-charge, but the calculations are not optimized for multi-orbit eclipse sequences common in low-inclination orbits.

This optimization task focuses on improving the accuracy and efficiency of power budget calculations during extended eclipse sequences. The system must correctly model eclipse fraction across consecutive orbits, account for panel degradation over mission lifetime, and maintain accurate depth-of-discharge tracking for battery health monitoring.

The optimized calculations should reduce unnecessary heater cycling during eclipse transitions and provide more accurate charge time estimates for mission planning.

### Acceptance Criteria

- Eclipse drain calculations correctly account for consumption during dark periods only
- Solar panel output uses proper angle-to-radians conversion for panel pointing
- Battery state-of-charge calculations produce values in the expected [0, 1] range
- Depth-of-discharge correctly reflects battery usage (1 - SOC relationship)
- Power mode thresholds trigger at documented SOC levels (critical < 0.1, low < 0.3)
- Panel degradation models exponential decay over mission lifetime
- Charge time estimates account for current battery level, not just capacity
- Eclipse fraction calculations integrate correctly with orbital period computations
- Total power aggregation correctly sums all power sources
- All existing power management tests continue to pass

### Test Command

```bash
cargo test
```

---

## Task 4: Ground Station Network API Extension (API Extension)

### Description

The mission operations team requires an extended API for ground station network management to support the upcoming multi-mission operations center. The current routing module provides basic link budget and ground station selection, but lacks comprehensive coverage for handover orchestration, failover routing, and link quality monitoring.

The API extension must expose endpoints for real-time link margin monitoring, automatic handover sequencing between ground stations, and failover route computation. The system should integrate with existing antenna gain calculations and support both S-band and X-band frequency planning.

Additionally, the API must provide predictive contact scheduling that accounts for Doppler shift compensation requirements and slant range variations during a pass.

### Acceptance Criteria

- Link margin API returns signal-to-noise in correct polarity (signal minus noise)
- Free-space path loss calculations include full 20*log10 terms for both distance and frequency
- Ground station visibility checks use inclusive comparison for minimum elevation angles
- Best ground station selection returns the station with minimum latency
- Handover sequencing returns the next station in sequence after the current contact
- Failover route computation excludes the failed primary station from backup list
- Link budget calculations correctly subtract losses from power plus gains
- Azimuth normalization operates on full 360-degree range
- Line-of-sight determination returns true for positive elevation angles
- Doppler shift calculations return correct sign for approaching/receding geometry
- All existing communication and routing tests continue to pass

### Test Command

```bash
cargo test
```

---

## Task 5: Resilience Framework Migration to Circuit Breaker 2.0 (Migration)

### Description

The current resilience framework implements a basic circuit breaker pattern, but operations has requested migration to an enhanced Circuit Breaker 2.0 specification that includes improved failure window detection, half-open state management, and cascade failure prevention.

The migration involves updating the retry backoff strategy from linear to true exponential growth, implementing accurate failure window detection for time-bounded failure counting, and ensuring the half-open state correctly limits probe requests. The cascade failure detection must trigger on any single dependency failure, not require all dependencies to fail.

This migration is critical for improving system reliability during ground station outages and inter-satellite link disruptions. The migration must be backward compatible with existing resilience tests while enabling new monitoring capabilities.

### Acceptance Criteria

- Retry delay implements true exponential backoff (base * 2^attempt pattern)
- Circuit breaker trips at the threshold value (not threshold + 1)
- Half-open state allows requests when current probes are below maximum
- Failure window detection returns true when last failure is within the window
- Cascade failure triggers when any single dependency has failed
- State duration correctly converts from milliseconds to seconds
- Fallback value returns primary when primary is OK, fallback otherwise
- Circuit reset logic checks open state (not closed) before allowing reset
- Recovery rate calculates recovered/total (not inverted)
- Bulkhead remaining permits returns (total - used)
- Degradation level thresholds trigger in correct order (high error rate = critical)
- Checkpoint intervals apply full multiplier without division
- All existing resilience and recovery tests continue to pass

### Test Command

```bash
cargo test
```
