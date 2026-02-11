# Scenario 001: Ambulance Routing Chaos

## Incident Report

**Incident ID**: INC-2024-0847
**Severity**: P1/Critical
**Status**: Open - Engineering Investigation
**Reported By**: Metro Regional Dispatch Center
**Date**: 2024-03-15 14:23 UTC

---

### Executive Summary

Multiple dispatch centers have reported that ambulance units are being assigned to incidents in ways that dramatically increase response times. Patients in critical condition are waiting significantly longer for emergency medical services.

---

### Timeline of Events

**14:00 UTC** - Shift supervisor at Metro West Dispatch notices ambulance Unit-47 was assigned to a cardiac arrest call 12 miles away while Unit-23 was available 0.8 miles from the scene.

**14:08 UTC** - Second report from Metro East: Unit-89 dispatched across the city for a trauma call when Unit-55 was in the same neighborhood.

**14:15 UTC** - Pattern confirmed: The routing system appears to be sending the FARTHEST available unit to every incident instead of the nearest one.

**14:23 UTC** - Incident escalated to Engineering. Temporary workaround: dispatchers manually overriding all automated assignments.

---

### Observed Symptoms

1. **Inverted Unit Selection**: When multiple units are available, the system consistently picks the one with the longest ETA rather than the shortest.

2. **ETA Calculations Appear Wrong**: For a 5-mile distance at 30 mph average speed, the system shows ETA of "0 minutes" instead of approximately 10 minutes. Dispatchers report all ETAs seem truncated or nonsensical.

3. **Regional Filtering Backwards**: When an incident occurs in Region "North", the system returns units from every region EXCEPT North.

4. **Route Scoring Paradox**: Higher-scoring routes (which should be better) actually have longer travel times. It seems like distance is being rewarded rather than penalized.

5. **Batch Dispatch Broken**: When assigning units to multiple simultaneous incidents, all incidents get assigned the same unit regardless of their locations.

---

### Impact Assessment

- **Response Time Degradation**: Average response time increased from 8 minutes to 23 minutes
- **Patient Outcomes**: 3 cases where delayed response contributed to adverse outcomes
- **Dispatcher Workload**: 100% manual override required, reducing throughput by 60%
- **Compliance Risk**: State-mandated response time SLAs being violated

---

### Systems Affected

- `routing` package - unit selection and scoring
- `services/routing` - route optimization service
- Related: capacity filtering may also be involved

---

### What We've Tried

- Restarted routing service - no improvement
- Verified unit GPS data is accurate - data is correct
- Checked network latency to routing service - normal
- Confirmed database has correct unit locations - data is valid

---

### Questions for Investigation

1. Why is the nearest-unit algorithm returning the farthest unit?
2. What's wrong with ETA estimation that makes everything show as 0 or near-0 minutes?
3. Why does region filtering exclude the target region instead of including it?
4. Is the route scoring formula adding distance as a bonus instead of a penalty?
5. Why does batch routing assign the same unit to all incidents?

---

### Stakeholder Contact

- Dispatch Operations: dispatch-ops@metroems.gov
- Medical Director: dr.chen@metroems.gov
- Compliance Officer: compliance@metroems.gov

---

*This incident is being tracked for regulatory reporting purposes. Resolution urgency: CRITICAL.*
