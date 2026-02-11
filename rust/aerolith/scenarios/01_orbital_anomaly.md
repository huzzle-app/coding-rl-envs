# Scenario 01: Orbital Period Anomaly Causing Power Deficits

## Incident Report - AERO-INC-2024-0847

**Filed by:** Mission Control - LEO Cluster Alpha
**Severity:** P1 - Critical
**Status:** Open
**Affected Satellites:** SAT-A017, SAT-A023, SAT-A031, SAT-A042

---

### Summary

Multiple satellites in the LEO Alpha cluster are experiencing unexplained power deficits during what should be sunlit portions of their orbit. The power management system is predicting sufficient solar generation, but actual battery state-of-charge is dropping faster than expected. Two satellites have entered safe mode due to critically low battery.

### Timeline

**14:23 UTC** - SAT-A017 telemetry shows battery SOC dropping despite predicted solar generation
**14:41 UTC** - SAT-A023 reports similar power deficit anomaly
**15:02 UTC** - SAT-A017 enters safe mode (SOC < 10%)
**15:18 UTC** - Power planning team notices eclipse duration predictions are inconsistent with ground-based tracking
**15:34 UTC** - SAT-A031 and SAT-A042 flagged for power anomalies
**16:05 UTC** - Manual command override to extend battery conservation mode cluster-wide

### Observed Symptoms

1. **Orbital period calculations appear incorrect**
   - Ground tracking shows 92.4 minute orbital period
   - Onboard system is computing significantly different values
   - Eclipse start/end predictions are off by several minutes

2. **Solar panel output is wrong**
   - Panels oriented at 15 degrees off-sun should produce ~97% output
   - System is reporting wildly incorrect values (sometimes negative)
   - Engineers suspect angle-to-output conversion is broken

3. **Battery state-of-charge reporting issues**
   - SOC values sometimes exceed 100% or show impossible ratios
   - Charge time estimates are completely unreliable
   - Depth-of-discharge readings don't match expected values

4. **Eclipse drain calculations fail**
   - System appears to compute eclipse drain backwards
   - Higher eclipse fraction results in LOWER predicted drain
   - Power budget planning is ineffective as a result

5. **Solar flux calculations at varying distances**
   - For satellites in elliptical transfer orbits
   - Solar flux doesn't decrease properly with distance
   - Inverse-square law not being applied correctly

### Impact

- 2 satellites in safe mode, unable to perform primary mission
- 6 additional satellites at risk of power deficit
- Scheduled science observations cancelled
- Estimated $2.4M in lost mission time

### Engineering Notes

The power management module relies on accurate orbital mechanics to predict eclipse windows. If the orbital period is being computed incorrectly, all downstream calculations will be wrong.

Additionally, the solar panel output function needs to handle angle inputs correctly - there may be a unit conversion issue.

The battery calculations seem to have basic arithmetic errors - ratios inverted, signs wrong, or operations swapped.

### Files of Interest

- `src/orbit.rs` - Orbital mechanics calculations
- `src/power.rs` - Power budget and battery management
- `src/scheduling.rs` - Eclipse timing and contact windows

### Reproduction

```bash
cargo test orbital
cargo test power
cargo test eclipse
```

Test failures should help isolate the specific calculation errors.
