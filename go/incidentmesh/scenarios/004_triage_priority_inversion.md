# Scenario 004: Triage Priority Inversion

## Support Ticket

**Ticket ID**: SUP-2024-1923
**Priority**: P2/High
**Category**: Clinical Operations
**Submitted By**: Dr. Maria Santos, Emergency Medicine Director
**Date**: 2024-03-18

---

### Problem Description

Our triage nurses and physicians have noticed that the IncidentMesh triage system is producing inconsistent and sometimes dangerous priority assignments. Patients with clearly critical conditions are being classified as "low priority" while less urgent cases receive elevated status.

---

### Specific Issues Reported

#### Issue 1: Classification Always Returns "Low"

A patient presented with:
- Severity: 5 (maximum)
- Criticality: 8 (life-threatening)

The system classified this as **"low"** priority. The triage nurse manually overrode to "critical" but this should never happen for a severity-5 case.

#### Issue 2: Severity Weighting Seems Linear

Our triage policy uses exponential severity weighting because the difference between severity 4 and 5 should be much larger than between 1 and 2. Currently:
- Severity 1 = 1.5 points
- Severity 5 = 7.5 points (linear: 5 * 1.5)

Expected (exponential):
- Severity 1 = 1.5 points
- Severity 5 = 7.59 points (1.5^5)

This flattens the priority curve for critical patients.

#### Issue 3: Criticality Reduces Priority

When criticality increases, the boost value DECREASES. A criticality of 5 gives a lower boost than criticality of 1. This is backwards - higher criticality should mean higher priority boost.

#### Issue 4: Batch Priorities Unsorted

When we review a batch of 10 waiting patients, the priority scores are returned in random order instead of highest-first. Nurses have to mentally sort the list, which wastes critical time.

#### Issue 5: Triage Policy Ignored

We have three triage policies configured:
- "strict" - for mass casualty events
- "normal" - standard operations
- "relaxed" - low-volume periods

Regardless of which policy we select, all patients get the same "default" category. The policy parameter has no effect.

#### Issue 6: Min/Max Functions Swapped

When checking "minimum severity in waiting patients", we get the maximum. When checking "maximum criticality", we get the minimum. This affects our dashboard displays.

#### Issue 7: Threshold Boundary Errors

Patients with severity exactly equal to our threshold (e.g., severity=4 for "critical" cutoff) are being placed in the lower category. A severity-4 patient shows as "moderate" instead of "critical".

#### Issue 8: Division by Zero Crashes

The urgency calculation crashed when a patient had severity=0 (observation-only cases). The application logged:
```
panic: runtime error: integer divide by zero
goroutine 47 [running]:
incidentmesh/internal/triage.UrgencyRank(...)
```

#### Issue 9: Normalized Priority Always 1.0

The normalized priority (0-1 scale) returns 1.0 for every patient regardless of their actual score. A patient with score 20 out of 100 max shows as 1.0 instead of 0.2.

#### Issue 10: Urgency Truncation

Total urgency for a batch of patients seems to lose decimal precision. Individual urgency scores like 45.7 and 32.3 sum to 77.0 instead of 78.0. The fractional parts are being dropped.

---

### Impact on Clinical Operations

1. **Patient Safety**: Critical patients may be deprioritized
2. **Resource Allocation**: Units calculated incorrectly for incident severity
3. **Compliance**: State triage protocols not being followed
4. **Staff Trust**: Nurses losing confidence in automated triage

---

### Requested Resolution

Please review the entire triage engine for logic errors. Every function that deals with severity, criticality, or priority calculation seems to have some kind of bug.

---

### Attachments

- Screenshot of misclassified severity-5 patient
- Batch priority output showing unsorted results
- Crash log from UrgencyRank function

---

*Escalation Note: If not resolved within 48 hours, we will disable automated triage and revert to manual paper-based triage.*
