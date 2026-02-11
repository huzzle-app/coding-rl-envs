# Post-Incident Review: Critical Incidents Not Escalating Properly

## PIR-2024-0120: Escalation and Queue Bypass Failures

**Incident Date**: 2024-01-20
**PIR Date**: 2024-01-22
**Facilitator**: Angela Rodriguez, VP Operations
**Attendees**: Platform Engineering, Dispatch Ops, Compliance

---

## Executive Summary

During the January 20th service disruption, we experienced cascading failures in our escalation and queue bypass systems. Critical incidents were not being escalated to the appropriate severity levels, and legitimate emergency queue bypasses were being rejected. This resulted in regulatory incidents going unnoticed for 4+ hours and emergency vehicles being stuck in standard queues.

---

## Incident Timeline

**06:00 UTC** - Routine operations begin

**07:23 UTC** - Hazmat spill reported on Route 15
- Severity Level: 8 (Critical)
- Affected Units: 12 vehicles
- Regulatory Flag: TRUE (environmental incident)
- **Expected Escalation**: Level 5 (maximum, immediate executive notification)
- **Actual Escalation**: Level 4 (delayed notification, no executive alert)

**07:45 UTC** - Second regulatory incident (safety violation)
- Severity: 8
- Affected: 10 units
- **Expected Escalation**: Level 4 minimum
- **Actual Escalation**: Level 3

**08:15 UTC** - Emergency response vehicles need queue bypass
- Escalation Level: 4
- Approvals: 2 (met requirement)
- Reason: "Emergency hazmat response deployment" (33 chars, meets 12 char minimum)
- **Expected**: Bypass APPROVED
- **Actual**: Bypass DENIED

**08:20 UTC** - Manual override attempted
- Override reason: "Regulatory emergency response required for hazmat incident" (57 chars)
- Approvals: 3
- TTL: 60 minutes
- **Expected**: Override APPROVED (reason > 12 chars, approvals >= 2, TTL <= 120)
- **Actual**: Override DENIED

**11:45 UTC** - Regulatory agency contacts CEO directly
- First executive notification of hazmat incident
- 4+ hours after initial report

---

## Root Cause Analysis

### Issue 1: Escalation Level Calculation

Test case analysis from incident:

| Severity | Impacted Units | Regulatory | Expected Level | Actual Level |
|----------|----------------|------------|----------------|--------------|
| 8        | 12             | true       | 5              | 4            |
| 8        | 10             | true       | 4              | 3            |
| 8        | 10             | false      | 3              | 2            |
| 5        | 15             | true       | 3              | 2            |

**Pattern**: Every escalation level is coming in 1 lower than expected.

Looking at the logic:
- Severity 8 should give base level 3, but appears to give level 2
- Severity 5 should give base level 2, but appears to give level 1
- Impact of 10+ units should add +1, but doesn't seem to trigger at exactly 10
- The regulatory +1 is working, but applied to an already-incorrect base

### Issue 2: Queue Bypass Rejection

Queue bypass requires:
1. Escalation Level >= 4 (need level 4 OR 5)
2. Approvals >= 2
3. Reason length >= 12 characters

Incident had:
- Escalation Level: 4 (should qualify)
- Approvals: 2 (should qualify)
- Reason: 33 characters (should qualify)

But bypass was DENIED. The check appears to require level > 4 (i.e., only level 5), not level >= 4.

### Issue 3: Override Rejection

Compliance override requires:
1. Reason length >= 12 characters (after trim)
2. Approvals >= 2
3. TTL <= 120 minutes

Incident had:
- Reason: 57 characters (should qualify)
- Approvals: 3 (should qualify)
- TTL: 60 minutes (should qualify)

But override was DENIED. Similar pattern - threshold check appears to be off.

---

## Impact Assessment

| Category | Count | Notes |
|----------|-------|-------|
| Regulatory incidents delayed | 2 | EPA and OSHA notifications late |
| Emergency bypasses denied | 7 | All should have been approved |
| Override requests denied | 4 | All met documented requirements |
| Total delay to executive notification | 4h 22m | Should have been immediate |
| Potential regulatory fines | $250,000 | EPA late notification penalty |

---

## Detailed Test Results

From QA reproduction:

### Escalation Level Tests

```
Test: severity=8, impactedUnits=10, regulatory=false
  Expected: base=3 + impact=1 = 4
  Actual: base=2 + impact=0 = 2
  FAILED

Test: severity=5, impactedUnits=10, regulatory=true
  Expected: base=2 + impact=1 + reg=1 = 4
  Actual: base=1 + impact=0 + reg=1 = 2
  FAILED

Test: severity=8, impactedUnits=11, regulatory=true
  Expected: base=3 + impact=1 + reg=1 = 5
  Actual: base=2 + impact=1 + reg=1 = 4
  FAILED (note: impact triggered at 11, not 10)
```

**Observation**:
- Severity >= 8 should give base 3, but > 8 is being used (never triggers at exactly 8)
- Impact >= 10 should add 1, but > 10 is being used (requires 11+)

### Bypass Tests

```
Test: escalationLevel=4, approvals=2, reasonLength=20
  Expected: ALLOWED
  Actual: DENIED
  FAILED

Test: escalationLevel=5, approvals=2, reasonLength=20
  Expected: ALLOWED
  Actual: ALLOWED
  PASSED (only level 5 works)
```

### Override Tests

```
Test: reasonLength=12 (exactly), approvals=2, ttl=60
  Expected: ALLOWED
  Actual: DENIED
  FAILED (12 chars not accepted, need 13+)
```

---

## Lessons Learned

1. **Boundary conditions matter**: All failures were at exact threshold values
2. **Testing gaps**: Unit tests didn't cover exact boundary cases
3. **Integration testing**: End-to-end escalation flow wasn't tested

---

## Action Items

| Action | Owner | Due |
|--------|-------|-----|
| Fix escalation level thresholds | Engineering | 2024-01-23 |
| Fix bypass level threshold | Engineering | 2024-01-23 |
| Fix override reason length threshold | Engineering | 2024-01-23 |
| Add boundary condition tests | QA | 2024-01-25 |
| Update runbooks with workarounds | Ops | 2024-01-24 |

---

## Files to Investigate

Based on the failures:
- Policy engine (escalation level calculation)
- Policy engine (queue bypass logic)
- Compliance ledger (override validation)

---

**Classification**: Internal - Regulatory Sensitive
**Distribution**: Engineering, Ops, Compliance, Legal
