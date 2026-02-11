# INCIDENT-2024-1847: Urgent Freight Dispatches Being Deprioritized

**Severity:** P1 - Critical
**Status:** Open
**Reported by:** Marcus Chen, Senior Dispatch Controller
**Date:** 2024-11-14 03:47 UTC
**Environment:** Production (APAC Region)

---

## Incident Summary

Multiple urgent freight dispatches with tight SLA windows are being assigned unexpectedly low priority scores, causing them to queue behind less time-sensitive shipments. Customer complaints about missed express delivery windows have increased 340% over the past 72 hours.

## Business Impact

- 47 SLA breaches in the past 24 hours for premium-tier customers
- Estimated penalty exposure: $2.1M in contractual SLA credits
- Three enterprise accounts have opened escalation tickets threatening contract review
- Operations team forced to manually override priority assignments for critical shipments

## Observed Behavior

When a shipment arrives with severity=7 (high priority) and an SLA window of 12 minutes remaining, the system assigns a priority score of approximately 35-50 instead of the expected 90+ range.

Example from dispatch logs:

```
[2024-11-14T03:12:47Z] DISPATCH job_id=FR-2024-847291
  severity=7 slaMinutes=12
  computed_priority=50
  expected_priority=~100
  queue_position=847 (!)
```

The priority seems to actually *decrease* when urgency increases, which is backwards from expected behavior.

## Reproduction Steps

1. Create a dispatch request with `severity: 7, slaMinutes: 12`
2. Observe the computed priority score
3. Compare against a dispatch with `severity: 7, slaMinutes: 45`
4. The longer SLA window actually receives a *higher* priority

## Related Test Failures

```
npm test -- tests/unit/dispatch.test.js
npm test -- tests/integration/flow-orchestration.test.js
```

Look for failures in:
- `assignPriority combines severity and sla urgency`
- Priority calculation tests with severity 7 edge cases

## Investigation Notes

- The `assignPriority` function in `src/core/dispatch.js` is the entry point
- Urgency bonus should be *added* to base priority, not subtracted
- Severity thresholds may also be off - severity 7 should qualify as "high priority"
- The 16-20 minute SLA window appears to receive no urgency bonus at all

## What We've Tried

- Restarting dispatch workers (no effect)
- Verifying input data integrity (data is correct)
- Rolling back recent config changes (no config changes in past week)

## Stakeholder Communication

Customer Success is requesting a root cause by EOD. Operations is currently running manual priority overrides but this is not sustainable.

---

**Assignee:** Unassigned
**Labels:** dispatch, priority, sla, p1-critical
