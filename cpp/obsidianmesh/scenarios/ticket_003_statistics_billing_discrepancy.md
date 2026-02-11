# SUPPORT-47823: Billing Discrepancies in Weighted Cargo Calculations

**Priority**: High
**Status**: Engineering Review
**Created**: 2024-03-12 09:15 PST
**Customer**: Maersk Line (Enterprise)
**Account Value**: $4.2M ARR

---

## Customer Report

> "Our March invoices show significant discrepancies from our internal calculations. The weighted cargo fees are consistently higher than expected. We've triple-checked our inputs and the formulas in our contract. Something is wrong on your end."
>
> -- Thomas Andersen, Maersk Finance Director

---

## Issue Details

### Customer-Reported Discrepancy

| Invoice Line | Maersk Calculation | ObsidianMesh Invoice | Difference |
|--------------|-------------------|---------------------|------------|
| Weighted Cargo Fee | $23,333.33 | $46,666.67 | +$23,333.34 |
| EMA-based Rate | $22.50/unit | $17.50/unit | -$5.00/unit |
| Correlation Surcharge | 5% | 21% | +16% |

### Reproducible Example

Customer provided calculation:
```
Values: [10, 20, 30]
Weights: [1, 2, 3]

Expected weighted mean:
  (10*1 + 20*2 + 30*3) / (1+2+3)
  = (10 + 40 + 90) / 6
  = 140 / 6
  = 23.333...

Your system returns: 46.666...
```

---

## Engineering Analysis

### Test Failures Identified

```
FAILED: stats_weighted_mean
  weighted_mean({10,20,30}, {1,2,3})
  Expected: 23.333
  Actual: 46.666

FAILED: stats_ema
  exponential_moving_average({10,20,30}, 0.5)
  Expected: 22.5
  Actual: 17.5
  Note: EMA appears to weight old values more than new

FAILED: stats_correlation
  correlation({1,2,3}, {2,4,6})
  Expected: 1.0 (perfect positive correlation)
  Actual: ~4.5 (impossible value, should be [-1, 1])

FAILED: stats_covariance
  covariance({1,2,3}, {4,5,6})
  Expected: 1.0
  Actual: ~7.33
```

### Weighted Mean Investigation

The weighted mean calculation divides by `values.size()` (count of values) instead of the sum of weights. This causes consistent over-billing when weights sum to less than the count of values.

```
Incorrect: weighted_sum / values.size()
           = 140 / 3 = 46.666

Correct:   weighted_sum / sum_of_weights
           = 140 / 6 = 23.333
```

### EMA Investigation

The exponential moving average applies alpha incorrectly:
- Should be: `alpha * new_value + (1-alpha) * old_ema`
- Appears to be: `(1-alpha) * new_value + alpha * old_ema`

This reverses the smoothing direction, giving too much weight to historical values.

### Correlation Issue

Correlation calculation uses `stddev(x) * stddev(x)` instead of `stddev(x) * stddev(y)`, producing invalid values outside the [-1, 1] range.

---

## Financial Impact

### Maersk Account
- Overbilled in March: ~$847,000
- Potential Q1 overbilling: ~$2.4M
- Credit/refund exposure: Full Q1 billing under review

### Other Customers at Risk
- Any customer using weighted cargo rates
- Customers on EMA-based dynamic pricing
- Correlation-based surcharge customers

Estimated total exposure: $12-15M across customer base.

---

## Affected Components

- `src/statistics.cpp` - weighted_mean, exponential_moving_average, covariance, correlation
- Billing service (consumes statistics module)
- Rate calculation engine

---

## Recommended Actions

1. **Immediate**: Issue billing hold for weighted cargo line items
2. **Short-term**: Credit affected customers while fix is developed
3. **Medium-term**: Full audit of Q1 billing using corrected formulas
4. **Long-term**: Add billing reconciliation checks against reference implementation

---

## Customer Communication

Draft response sent to customer success for review:

> "We have identified the root cause of the billing discrepancy. Our weighted mean calculation contained a formula error. We are issuing a credit for the full difference and will provide updated invoices within 5 business days. We deeply apologize for the inconvenience."

---

## Test Cases to Verify Fix

```cpp
// weighted_mean({10,20,30}, {1,2,3}) == 23.333
// exponential_moving_average({10,20,30}, 0.5) == 22.5
// covariance({1,2,3}, {4,5,6}) == 1.0
// correlation({1,2,3}, {2,4,6}) == 1.0
// correlation({1,2,3}, {6,4,2}) == -1.0
```

---

## References

- Customer contract: MAERSK-2023-ENT-0047
- Billing service: billing-service-v2.3.1
- Statistics module: `src/statistics.cpp`
- Related tests: `tests/test_main.cpp` lines 549-632
