# Customer Escalation: Subscription Billing Discrepancies

## Zendesk Ticket #91203

**Priority**: Urgent
**Customer**: Multiple affected (23 reports in 48 hours)
**Team**: Billing & Payments
**Created**: 2024-02-14 09:15 UTC
**Status**: Escalated to Engineering

---

## Summary

Multiple customers are reporting incorrect charges during subscription plan changes. Issues include:
1. Overcharges when upgrading plans mid-cycle
2. Immediate loss of access after cancellation
3. Double charges for the same subscription period

---

## Customer Reports

### Case 1: Proration Overcharge
**Customer**: james.wilson@example.com (Premium subscriber)

> "I upgraded from Basic ($9.99) to Premium ($14.99) with 15 days left in my billing cycle. I expected to pay around $2.50 for the difference, but I was charged $7.50. The math doesn't add up."

**Account Details**:
```
Previous Plan: Basic ($9.99/month)
New Plan: Premium ($14.99/month)
Days Remaining: 15 out of 30
Expected Proration: (14.99/30 - 9.99/30) * 15 = $2.50
Actual Charge: $7.50
```

### Case 2: Immediate Access Loss on Cancel
**Customer**: sarah.chen@example.com (Family subscriber)

> "I canceled my subscription on Feb 12 but my billing period doesn't end until Feb 28. Why was my access revoked immediately? I already paid for the full month!"

**Account Timeline**:
```
Feb 1: Billing cycle started, $22.99 charged
Feb 12: User clicked "Cancel Subscription"
Feb 12: Access immediately revoked (should be Feb 28)
```

### Case 3: Double Upgrade Charge
**Customer**: marcus.johnson@example.com

> "I tried to upgrade to Premium but got an error. Clicked retry once and now I've been charged twice - once for $4.99 and once for $5.01. Both for the same upgrade."

**Payment History**:
```
2024-02-14 14:32:01.234 - Charge $4.99 - upgrade_proration - SUCCESS
2024-02-14 14:32:01.567 - Charge $5.01 - upgrade_proration - SUCCESS
```

---

## Internal Slack Thread

**#billing-eng** - February 14, 2024

**@billing-support** (10:30):
> We've had 23 proration complaints in the last 48 hours. Some customers are being overcharged, others undercharged. The amounts are always slightly off from what they should be.

**@eng-david** (10:45):
> I'm looking at the proration calculation. There's definitely something wrong with the math. For a Basic->Premium upgrade with 15 days left:
> ```
> Credit: 9.99/30 * 15 = 4.995
> Cost: 14.99/30 * 15 = 7.495
> Expected: 7.495 - 4.995 = 2.50
> Actual from logs: 7.50
> ```
> The decimal handling looks suspicious.

**@eng-maria** (11:02):
> The double charge issue is worse. Looking at the logs:
> ```
> 14:32:01.234Z [subscription] Creating upgrade for user_123
> 14:32:01.234Z [subscription] Fetching existing subscription
> 14:32:01.235Z [subscription] Creating upgrade for user_123  <-- duplicate!
> 14:32:01.235Z [subscription] Fetching existing subscription
> 14:32:01.340Z [payment] Charging user_123: $4.99
> 14:32:01.567Z [payment] Charging user_123: $5.01
> ```
> Two concurrent requests are both getting through. There's no lock.

**@eng-david** (11:15):
> And the cancellation issue - when we set status to 'canceled', the access check is failing. Let me trace through...

**@eng-david** (11:28):
> Found it. The `hasFeature` check doesn't distinguish between `canceling` (still has access) and `canceled` (no access). We're setting status directly to `canceled` instead of `canceling`.

**@billing-support** (11:35):
> This is getting worse. We now have a customer who got charged correctly but shows wrong features. They're paying for Premium but only getting Basic features.

---

## Technical Investigation

### Proration Calculation Trace

```javascript
// Logged values for user james.wilson@example.com upgrade
{
  oldPlan: { price: 9.99 },
  newPlan: { price: 14.99 },
  daysRemaining: 15,
  totalDays: 30,

  // Calculated values
  oldDailyRate: 0.333,        // 9.99/30 = 0.333 (truncated)
  newDailyRate: 0.4996666..., // 14.99/30 (floating point)
  credit: 4.995,              // 0.333 * 15
  cost: 7.495,                // 0.4996... * 15

  // Final amount
  rawDifference: 7.495 - 4.995 = 2.500...,
  afterRounding: 7.50  // BUG: This is wrong!
}
```

### Race Condition Evidence

Request log showing concurrent upgrade attempts:
```
[2024-02-14T14:32:01.234Z] POST /subscriptions/upgrade user=marcus.johnson
[2024-02-14T14:32:01.235Z] POST /subscriptions/upgrade user=marcus.johnson
[2024-02-14T14:32:01.340Z] Payment processed: $4.99
[2024-02-14T14:32:01.567Z] Payment processed: $5.01
[2024-02-14T14:32:01.890Z] Subscription updated: premium
[2024-02-14T14:32:01.892Z] Subscription updated: premium
```

### Cancellation Flow

```
Expected:
  cancel() -> status = 'canceling' -> access continues until periodEnd

Actual:
  cancel() -> status = 'canceled' -> access immediately revoked
```

---

## Metrics Dashboard

```
Proration Accuracy (last 7 days):
  Feb 8-10: 99.8% within $0.01 tolerance
  Feb 11-14: 67.3% within $0.01 tolerance  <-- dropped after deploy

Double Charge Rate:
  Normal: <0.01%
  Current: 2.3% (230x increase)

Premature Access Revocation:
  Feb 12: 47 users affected
  Feb 13: 89 users affected
  Feb 14: 156 users affected (trending up)
```

---

## Financial Impact

- **Overcharges to refund**: $1,847.23 (estimated)
- **Support tickets**: 23 high-priority, 45 medium
- **Churn risk**: 12 users mentioned canceling due to billing issues
- **Trust impact**: 3 social media complaints

---

## Recent Deployments

- Feb 11: billing-service v3.2.0 deployed (subscription refactor)
- Feb 11: Updated proration calculation "for precision"
- Feb 12: No deployments

---

## Files to Investigate

- `services/billing/src/services/subscription.js` - Proration, cancellation logic
- Race condition in upgrade flow
- Feature access check logic

---

**Status**: CRITICAL
**Assigned**: @billing-eng, @payments-team
**Next Steps**: Immediate hotfix for double charges, then proration fix
