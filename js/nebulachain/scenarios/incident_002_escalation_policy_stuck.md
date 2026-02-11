# Incident Report INC-2024-0903

## Classification
- **Priority**: P2 - High
- **Status**: Open
- **Service**: NebulaChain Supply Provenance Platform
- **Component**: Policy Escalation Engine
- **Reported By**: Fraud Prevention Team
- **Date**: 2024-11-18T14:22:00Z

## Executive Summary

The fraud policy escalation system is not triggering escalations when it should. Dispatches experiencing repeated failures remain at "normal" policy level instead of escalating to "watch" or "restricted" status. Additionally, once policies do escalate, they require an excessive number of successes before de-escalating.

## Impact

- **Security Risk**: 12 potentially fraudulent dispatch patterns went undetected for 4+ hours
- **False Negatives**: Estimated 340 high-risk shipments processed without additional verification
- **Compliance**: Audit trail shows policy state not matching actual risk conditions
- **Operations**: When escalation finally triggers, dispatches get stuck in "restricted" state indefinitely

## Symptoms

### 1. Escalation Not Triggering

When a dispatch experiences exactly 2 consecutive failures, the policy remains at "normal" instead of escalating:

```
[14:18:32.441Z] WARN policy: dispatch DSP-78234 failure_burst=2 current_policy=normal
[14:18:32.442Z] INFO policy: nextPolicy result=normal (no escalation)
# Expected: should have escalated to "watch"

[14:19:01.223Z] WARN policy: dispatch DSP-78234 failure_burst=2 current_policy=normal
[14:19:01.224Z] INFO policy: nextPolicy result=normal (no escalation)
# Still not escalating despite repeated failures at burst=2
```

### 2. De-escalation Requires Too Many Successes

Once a policy does eventually escalate (after burst > 2), it requires 10 consecutive successes to de-escalate instead of the documented 8:

```
[15:02:14.881Z] INFO policy: de-escalation check policy=watch success_window=8
[15:02:14.882Z] INFO policy: shouldDeescalate result=false threshold=10
# Documentation states threshold should be 8

[15:04:22.103Z] INFO policy: de-escalation check policy=watch success_window=9
[15:04:22.104Z] INFO policy: shouldDeescalate result=false threshold=10
# 9 successes still not enough
```

### 3. Escalation Cooldown Too Long

The cooldown between escalation events appears to be 5 minutes instead of the expected 3 minutes, causing delayed response to emerging fraud patterns:

```
[15:10:00.000Z] INFO policy: escalation cooldown remaining=180000ms (expected)
# Actual observed: 300000ms (5 minutes)
```

## Affected Tests

- `hyper-matrix-00001` through `hyper-matrix-00500` - policy escalation assertions
- `hyper-matrix-01234`, `hyper-matrix-02468` - boundary condition failures
- Unit tests in `policy.test.js` - threshold comparisons
- `security-policy.test.js` integration tests

## Root Cause Hypothesis

The escalation threshold comparison may be using an inclusive operator (`<=`) when it should be exclusive (`<`), causing bursts of exactly 2 to not trigger escalation. Additionally:
- De-escalation threshold may be hardcoded to wrong value
- Cooldown constant may be set to 300000ms instead of 180000ms

## Business Context

Per the Global Provenance Security Framework (GPSF) v2.1:
- A failure burst of 2 MUST trigger escalation (Section 4.2.1)
- De-escalation requires 8 consecutive successes (Section 4.3.2)
- Escalation cooldown is 3 minutes (Section 4.2.4)

## Attachments

- policy_state_transitions_20241118.log
- fraud_detection_gap_analysis.xlsx
- gpsf_v2.1_requirements.pdf

---
**Incident Commander**: Marcus Rodriguez, Security Operations
**Next Update**: 2024-11-18T16:00:00Z
