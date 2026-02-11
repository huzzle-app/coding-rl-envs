# JIRA-AEGIS-1934: Policy Escalation Triggering on Single Failure

**Type**: Bug
**Priority**: High
**Component**: Policy Engine
**Reporter**: SRE Team Lead
**Created**: 2024-11-14 14:07 UTC

---

## Description

The AegisCore policy engine is escalating operational modes too aggressively. A single transient failure is causing the system to escalate from "normal" to "watch" mode, when the documented behavior states that escalation should only occur after multiple consecutive failures.

Additionally, once in an elevated state, the de-escalation logic appears to require one more success than the documented threshold before stepping down.

## Expected vs Actual Behavior

### Escalation (AGS-0008)

**Expected**: System remains in current policy when `failureBurst = 1`
**Actual**: System escalates to next policy level on exactly 1 failure

The policy documentation states:
> "Escalation occurs when failure burst exceeds the threshold (>1 failures)"

But the system is escalating on exactly 1 failure, suggesting a boundary condition error.

### De-escalation (AGS-0009)

**Expected**: System de-escalates when `successStreak >= threshold`
**Actual**: System requires `successStreak > threshold` (one extra success)

For "halted" state with threshold=10:
- Expected: De-escalate when successStreak reaches 10
- Actual: De-escalate only when successStreak reaches 11

## Impact

- False positives causing unnecessary operational restrictions
- Terminal crews manually overriding automated policy gates
- Delayed vessel departures during "watch" mode (average 23 minutes)
- De-escalation taking 10% longer than expected after incidents resolve

## Steps to Reproduce

### Escalation Issue
1. Start with policy in "normal" state
2. Record exactly 1 failure (`failureBurst = 1`)
3. Observe policy state changes to "watch" when it should remain "normal"

### De-escalation Issue
1. Put system in "halted" state
2. Record 10 consecutive successes
3. Check if `ShouldDeescalate(10, "halted")` returns true
4. It returns false; requires 11 successes

## Failing Tests

```
NextPolicyEscalates (boundary case)
ShouldDeescalateThresholds
```

## Technical Context

- `Policy.NextPolicy()` method handles escalation logic
- `Policy.ShouldDeescalate()` method handles de-escalation checks
- Both methods appear to have off-by-one errors at threshold boundaries

## Workaround (Temporary)

Operations team has increased the manual override approval threshold from P2 to P3 incidents to reduce false escalation impact.

---

**Labels**: boundary-condition, off-by-one, policy-engine
**Sprint**: Aegis-2024-Q4-S3
**Story Points**: 3
