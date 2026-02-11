# INCIDENT-2024-1847: Dispatch ETA Calculations Significantly Inaccurate

**Severity**: HIGH
**Status**: INVESTIGATING
**Detected**: 2024-03-15 14:22 UTC
**Duration**: Ongoing
**Affected Service**: heliosops-dispatch, heliosops-routing

---

## Summary

Multiple field units and dispatch supervisors report that Estimated Time of Arrival (ETA) values displayed in the dispatch console are wildly inaccurate. Units are arriving significantly earlier or later than predicted, causing resource planning failures and missed SLA targets.

## Timeline

- **14:22 UTC** - First report from District 7 supervisor: "Engine 47 was showing 23 minute ETA but arrived in 8 minutes"
- **14:35 UTC** - Second report from Metro Central: "Ambulance 12 showed 4 minute ETA, actually took 31 minutes"
- **14:41 UTC** - Pattern confirmed: ETA errors are not random, seem correlated with unit capabilities
- **15:02 UTC** - Engineering notified via PagerDuty
- **15:15 UTC** - Initial investigation started

## Observed Symptoms

### 1. ETA Inflation for Specialized Units
Units with specific certifications (HazMat, Technical Rescue, ALS) consistently show inflated ETAs even when physically close to the incident.

**Example**:
- HazMat Unit 3 located 2.1 km from chemical spill incident
- Displayed ETA: 52 minutes
- Actual arrival: 4 minutes
- Expected ETA at 60 km/h: ~2 minutes

### 2. ETA Deflation for Mismatched Units
When a unit type doesn't match the incident type, ETAs sometimes appear lower than reality.

**Example**:
- Police unit dispatched to structure fire (backup)
- Displayed ETA: 6 minutes
- Actual travel time: 18 minutes
- Distance was 15 km

### 3. Correlation with Capability Scoring
Operations team notes that the ETA errors seem to scale with what they call "capability mismatch" -- the worse the fit between unit type and incident type, the larger the ETA error.

## Impact

- **SLA Tracking**: 47 incidents incorrectly marked as "within SLA" that actually breached
- **Resource Planning**: Supervisors making assignment decisions based on wrong arrival estimates
- **Field Confusion**: Unit crews reporting dispatch console shows "impossible" ETAs

## Metrics

```
dispatch.eta.error_seconds (p99): 1,847s (expected < 180s)
dispatch.eta.error_seconds (p50): 423s (expected < 60s)
routing.distance_calculations: normal
dispatch.assignments.success_rate: 99.2% (normal)
```

## Initial Investigation Notes

- Routing distance calculations appear correct when tested in isolation
- Speed assumptions (60 km/h default) seem reasonable
- The error magnitude doesn't correlate with distance -- a 2km trip can have a larger absolute error than a 20km trip
- Something in the dispatch planning is using the wrong value for time estimation

## Questions for Engineering

1. What value is being used to calculate ETA in `plan_dispatch()`?
2. Is there any transformation or scoring applied before the ETA calculation?
3. Why would unit capabilities affect travel time estimates?

## Runbook Reference

See `runbooks/dispatch-eta-debugging.md` for standard ETA investigation procedures.

---

**Assigned To**: On-call SRE
**Escalation Path**: dispatch-team@heliosops.internal
**Related Alerts**: ALERT-7742, ALERT-7756
