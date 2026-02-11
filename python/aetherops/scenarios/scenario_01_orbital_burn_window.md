# Scenario 01: Suboptimal Burn Window Selection

## Incident Report: INC-2026-0134

**Reported by:** Mission Planning Lead - Dr. Sarah Chen
**Severity:** High
**Affected System:** Orbital Mechanics / Burn Planner
**Date:** 2026-01-15 08:42 UTC

---

### Summary

The burn window selection algorithm is consistently choosing inefficient windows for orbital corrections. Flight dynamics has observed that the selected windows provide significantly lower delta-v efficiency than expected.

### Observed Behavior

When presented with multiple burn windows for a given maneuver requirement, the system selects windows that provide the **worst** delta-v budget per unit time, rather than the best. This has led to:

- Extended maneuver durations
- Higher cumulative fuel consumption across burn sequences
- Missed opportunities for optimal correction windows

### Business Impact

- Starlink-7 constellation required 40% more fuel for station-keeping last month
- Two commercial satellite repositioning contracts exceeded fuel budgets
- Customer escalation from Orbital Dynamics Ltd regarding burn efficiency

### Reproduction Steps

Given three burn windows with varying delta-v budgets and durations:
- Window A: 2.5 delta-v over 100 seconds (0.025 per second)
- Window B: 1.2 delta-v over 30 seconds (0.040 per second)
- Window C: 3.0 delta-v over 200 seconds (0.015 per second)

The algorithm selects Window C (worst efficiency) instead of Window B (best efficiency).

### Failed Tests

```
tests/unit/orbit_test.py::OrbitTest::test_optimal_window_selection
tests/stress/hyper_matrix_test.py::test_burn_window_efficiency_*
```

### Investigation Notes

The selection criteria in `aetherops/orbit.py` appears to be inverted. Review the `optimal_window` function and verify it returns the window with **maximum** delta-v efficiency, not minimum.

---

### Attachments

- Fuel consumption report: Q4-2025-fuel-variance.pdf
- Customer complaint: orbital-dynamics-escalation-0134.eml
