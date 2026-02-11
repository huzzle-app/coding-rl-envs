# Alert Runbook: Compliance Override and Authorization Failures

**Alert Name**: `clearledger_compliance_override_rejected`
**Severity**: P2 - High
**Runbook Version**: 2.1
**Last Updated**: 2024-01-16

---

## Alert Description

This alert fires when legitimate compliance overrides are being rejected despite meeting all documented requirements, or when authorization/audit checks are producing unexpected results.

## Current Incident

**Triggered**: 2024-01-16 08:45 UTC
**Status**: Investigating

### Symptoms Observed

1. **Override Rejection with Valid Inputs**
   Compliance team reports that override requests with proper justification and dual approval are being rejected.

   ```
   reason: "Emergency settlement required per regulatory mandate"  (47 chars)
   approvals: 2
   ttl_minutes: 60

   Result: REJECTED
   Expected: APPROVED
   ```

2. **Requires MFA Check Too Narrow**
   The `requires_mfa?` function is only triggering MFA for "override" action but not for "settle" which should also require MFA per policy.

   ```ruby
   Authz.requires_mfa?('settle')
   # Expected: true (settle requires MFA per policy)
   # Actual: false
   ```

3. **Audit Required Check Incomplete**
   The CommandRouter `requires_audit?` check only includes "settle" but misses "reconcile" actions:

   ```ruby
   CommandRouter.requires_audit?('reconcile')
   # Expected: true (reconcile needs audit trail)
   # Actual: false
   ```

4. **Compliance Audit Check Missing Action**
   The Compliance `audit_required?` function only checks for "settle" and "override" but misses "reconcile":

   ```ruby
   Compliance.audit_required?('reconcile')
   # Expected: true
   # Actual: false
   ```

5. **Command Priority Incorrect**
   Settlement commands are getting priority 0 (lowest) when they should be highest priority:

   ```ruby
   CommandRouter.command_priority('settle')
   # Expected: 3 (highest priority)
   # Actual: 0 (falls through to else)
   ```

---

## Troubleshooting Steps

### Step 1: Verify Override Request Parameters

Check that the override request meets minimum requirements:
- Reason length >= 10 characters (documented requirement)
- Approvals >= 2
- TTL <= 120 minutes

```ruby
reason = "Emergency settlement required per regulatory mandate"
reason.length  # => 47, should be sufficient
```

### Step 2: Check Override Logic

The rejection suggests the validation thresholds may be incorrect:

```ruby
# Current behavior suggests it requires MORE than documented minimums
Compliance.override_allowed?(
  "Short reason",  # 12 chars exactly
  2,               # exactly 2 approvals
  120              # exactly 120 min TTL
)
# This should return true but may be returning false
```

### Step 3: Verify Policy Compatibility

The `policy_compatible?` function may have inverted logic:

```ruby
Compliance.policy_compatible?(3, 5)
# If v1=3 can run on v2=5, should return true
# Check if comparison direction is correct
```

### Step 4: Check SLA Boundary Conditions

Related SLA `sla_met?` check may have similar boundary issues:

```ruby
SLA.sla_met?(100, 100)
# Elapsed equals target exactly
# Expected: probably true (met at boundary)
# Check: is it using < instead of <=?
```

---

## Impact Assessment

| Area | Impact |
|------|--------|
| Compliance Overrides | Valid overrides rejected, manual escalation required |
| Audit Trail | Reconcile actions not being logged |
| MFA Enforcement | Settle actions bypassing MFA requirement |
| Command Priority | Settlement commands deprioritized |
| Policy Migration | Unknown - may affect version compatibility |

## Escalation

If symptoms persist after 30 minutes:
1. Page on-call engineer via PagerDuty
2. Enable audit bypass mode (requires VP approval)
3. Switch to manual settlement workflow

## Related Alerts

- `authorization_mfa_bypass` - May fire if settle actions bypass MFA
- `audit_trail_incomplete` - Should fire for unlogged reconcile actions
- `command_priority_inversion` - Settle commands queued behind lower-priority

## Acceptance Criteria for Fix

- [ ] Overrides with reason >= 10 chars, 2+ approvals, TTL <= 120 min are accepted
- [ ] `requires_mfa?` returns true for both "override" and "settle"
- [ ] `requires_audit?` returns true for "settle" and "reconcile"
- [ ] `audit_required?` includes "reconcile" action
- [ ] `command_priority('settle')` returns highest priority (3)
- [ ] `sla_met?` correctly handles boundary case (elapsed == target)
- [ ] `policy_compatible?` returns true when v1 <= v2

## Notes

These issues suggest a pattern of:
1. Boundary condition errors (`>` vs `>=`, `<` vs `<=`)
2. Incomplete action lists in validation checks
3. Missing cases in priority/action routing
