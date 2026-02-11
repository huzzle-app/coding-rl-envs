# SUPPORT-4721: Allocation Cost Estimates Wildly Incorrect

**Ticket ID:** SUPPORT-4721
**Priority:** High
**Status:** Escalated to Engineering
**Created:** 2024-03-20 09:15 PST
**Customer:** Nexus AI Solutions (Enterprise Tier)
**Account Manager:** Sarah Chen
**Support Engineer:** Marcus Rodriguez

---

## Customer Report

> "We're seeing cost estimates that are completely wrong. When we dispatch a batch of 1000 inference requests at $0.002 per request, the system quotes us $2,000 instead of $2. This is making our finance team very nervous and we can't approve any new batch jobs until this is fixed. We've been a customer for 3 years and never seen anything like this."
>
> -- David Park, VP Engineering, Nexus AI Solutions

## Issue Details

**Environment:** Production (us-east-1)
**API Version:** v2.4.1
**Affected Endpoint:** `/v1/allocator/estimate`

The allocation cost estimation is returning values that are orders of magnitude too high. Investigation reveals the cost-per-unit calculation appears to be multiplying instead of dividing.

## Reproduction Steps

```bash
curl -X POST https://api.tensorforge.io/v1/allocator/estimate \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "total_cost": 2.00,
    "quantity": 1000,
    "model_id": "inference-standard-v2"
  }'
```

**Expected Response:**
```json
{
  "cost_per_unit": 0.002,
  "total_estimate": 2.00,
  "currency": "USD"
}
```

**Actual Response:**
```json
{
  "cost_per_unit": 2000.0,
  "total_estimate": 2000000.00,
  "currency": "USD"
}
```

## System Logs

```
[2024-03-20T16:42:18.334Z] allocator::cost_engine DEBUG
  operation=cost_per_unit
  total_cost=2.00
  quantity=1000
  computed_cpu=2000.0
  ANOMALY: cost_per_unit should be total_cost/quantity, got total_cost*quantity
```

## Additional Issues Reported

The customer also noted several other anomalies:

1. **Berth Utilization:** Dashboard shows 0% utilization when all berths are occupied
2. **Urgency Normalization:** Urgency scores clamped at 100 instead of 1.0, breaking priority calculations
3. **Priority Scoring:** Using floor division instead of ceiling, causing off-by-one allocation errors

## Failing Tests

Engineering confirmed the following test failures in CI:

- `test_cost_per_unit_calculation` - Division vs multiplication
- `test_berth_utilization_when_occupied` - Inverted occupancy filter
- `test_urgency_normalized_to_unit_interval` - Clamp range incorrect
- `test_priority_score_ceiling_division` - Floor vs ceiling
- `test_capacity_threshold_at_100_percent` - Boundary check
- `hyper_matrix_scenarios::allocator_*` - Allocation matrix tests

## Business Impact

- **Blocked Revenue:** Customer has paused $45,000/month in batch processing jobs
- **Trust Impact:** Customer questioning accuracy of all billing
- **Escalation Risk:** Customer requested call with VP of Engineering

## Customer Workaround

Advised customer to manually divide quoted costs by (quantity^2) as temporary workaround. Customer is not satisfied with this solution.

## Technical Notes

The allocator module contains several numerical calculation bugs:

1. `cost_per_unit` uses `*` operator instead of `/`
2. `berth_utilization` filters on `!occupied` instead of `occupied`
3. `normalize_urgency` clamps to `[0, 100]` instead of `[0, 1]`
4. `priority_score` uses floor division instead of ceiling

## Resolution Requirements

- Fix cost calculation formula
- Fix berth utilization filter logic
- Correct urgency normalization range
- Update priority score to use ceiling division
- Full regression test before deployment

## Attachments

- Customer screenshot of billing dashboard
- API request/response logs
- Comparison spreadsheet (expected vs actual)

---

**SLA Status:** Response SLA met (< 4 hours). Resolution SLA at risk.
**Next Update:** 2024-03-20 14:00 PST
