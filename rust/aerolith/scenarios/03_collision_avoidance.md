# Scenario 03: Collision Avoidance System Near-Miss

## Mission Anomaly Report - AERO-MAR-2024-0156

**Classification:** Safety Critical
**Review Board:** Constellation Safety Office
**Date:** 2024-03-15
**Status:** Root Cause Analysis Pending

---

### Executive Summary

On March 14, 2024, satellite SAT-B007 experienced a near-miss event with tracked debris object TLE-44891. The collision avoidance system failed to execute an emergency burn despite the object passing within 150 meters. Post-event analysis reveals multiple failures in the safety assessment chain.

### Event Reconstruction

**T-4 hours:** Space Surveillance Network updates conjunction data for SAT-B007
**T-3 hours:** Collision probability computed at 0.0021 (should have been higher)
**T-2 hours:** Threat level assessed as "2" (should have been "3")
**T-90 min:** Avoidance window computed incorrectly
**T-60 min:** No emergency burn commanded
**T-0:** Debris passes within 147m of SAT-B007 (miss distance < exclusion zone)
**T+10 min:** Post-pass telemetry confirms no impact

### Detailed Findings

#### 1. Collision Probability Underestimated

The collision probability calculation returned values approximately half of what they should be. Investigation suggests the geometric cross-section denominator uses an incorrect constant (2*pi instead of 4*pi in the spherical shell formula).

#### 2. Keep-Out Zone Boundary Error

Objects at EXACTLY the exclusion radius are not being flagged. A debris object at 500m when the exclusion radius is 500m shows as "safe" instead of triggering an alert. The boundary check appears to use strict inequality.

#### 3. Debris Density Model Wrong

The debris density calculation at altitude returns values that don't make physical sense. Instead of dividing by altitude (for a shell volume approximation), the system appears to divide by altitude squared.

#### 4. Threat Level Boundaries Off-By-One

Probability thresholds for threat levels are using strict greater-than comparisons:
- Probability of exactly 0.75 returns threat level 3, not 4
- Probability of exactly 0.50 returns threat level 2, not 3

This caused our 0.0021 (actual ~0.004) probability to be under-assessed.

#### 5. Avoidance Window Timing Inverted

The collision avoidance window calculation SUBTRACTS the lead time from the time of closest approach (TCA) instead of adding it. This means the "avoidance window" starts AFTER the conjunction instead of before.

#### 6. Conjunction Sorting Wrong

Conjunctions are sorted by distance in descending order (farthest first) instead of ascending (closest first). Risk prioritization is inverted.

#### 7. Exclusion Zone Radius Doubled

The exclusion zone radius calculation uses the full diameter of an object instead of its radius. All safety margins are 2x what they should be, which sounds safer but actually causes resource allocation issues.

#### 8. Fragmentation Risk Logic Inverted

The fragmentation risk assessment checks for velocity LESS than threshold instead of GREATER than. High-velocity impacts are being marked as "low" risk.

#### 9. Reentry Altitude Threshold Wrong

The reentry detection uses 150km threshold instead of 120km. Objects already in decay are not being tracked as re-entering.

#### 10. Risk Matrix Axes Swapped

The risk matrix score computation swaps severity and probability axes. A high-severity/low-probability event scores the same as a low-severity/high-probability event.

#### 11. Debris Count Ignores Size Filter

The debris counting function ignores the minimum size filter and counts ALL objects regardless of size.

#### 12. EVA Safety Check Incomplete

The EVA safety assessment only checks visibility and ignores debris count entirely.

### Recommendations

1. Immediate code review of `src/safety.rs`
2. Audit all comparison operators (< vs <=, > vs >=)
3. Verify mathematical formulas against reference materials
4. Add boundary condition tests for all threshold functions

### Files to Investigate

- `src/safety.rs` - Collision risk assessment and avoidance logic

### Reproduction

```bash
cargo test safety
cargo test collision
cargo test debris
cargo test threat
cargo test exclusion
```
