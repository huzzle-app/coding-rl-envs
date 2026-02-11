# Executive Dashboard Alert: SLA Reporting Anomalies

## Weekly Ops Review - January 22, 2024

**Reported By**: CFO Office
**Priority**: Critical - Financial Reporting Impact
**Distribution**: C-Suite, Finance, Engineering, Operations

---

## Issue Summary

Our weekly SLA compliance report is showing significant discrepancies between actual service performance and reported metrics. Multiple categories of issues have been identified:

1. SLA breach classifications are incorrect
2. Percentile calculations for response times are wrong
3. Compliance data retention bucketing is off
4. Token freshness calculations causing false positives

---

## Dashboard Discrepancies

### SLA Breach Classification

From weekly report:

| Dispatch ID | ETA (sec) | SLA (sec) | Actual Delta | Expected Class | Reported Class |
|-------------|-----------|-----------|--------------|----------------|----------------|
| D-1001      | 3599      | 3600      | -1           | none           | none           |
| D-1002      | 3600      | 3600      | 0            | none           | minor          |
| D-1003      | 3900      | 3600      | +300         | minor          | major          |
| D-1004      | 4500      | 3600      | +900         | major          | critical       |

**Pattern**: Every classification is one severity higher than it should be at exact boundaries.

### Business Impact

When delta is exactly 0 (on-time delivery), the system reports it as "minor breach" instead of "none". This is affecting our SLA compliance metrics:

```
Week of Jan 15-21:
  Actual on-time rate: 94.2%
  Reported on-time rate: 91.8%
  Discrepancy: 2.4% (significant for bonus calculations)
```

---

## Finance Team Analysis

### Breach Risk False Positives

The breach risk indicator is also triggering incorrectly:

```
SLA: 3600 seconds
Buffer: 300 seconds
ETA: 3300 seconds (exactly at SLA - buffer boundary)

Expected: breachRisk = false (3300 is NOT greater than 3300)
Actual: breachRisk = true
```

This causes unnecessary pre-emptive alerts and resource reallocation when we're exactly at the safe boundary.

### P99 Latency Calculation

Statistics team flagged percentile calculations as inaccurate:

```
Test dataset: [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
10 values, sorted

P99 (99th percentile):
  Expected index: floor(0.99 * (10-1)) = floor(8.91) = 8 -> value 900
  Actual calculation: round(0.99 * 10) = 10 -> value 1000 (out of bounds, clamped)

P50 (median):
  Expected: value at index 4 or 5 (450 interpolated, or 500)
  Actual: round(0.50 * 10) = 5 -> value 600 (off by one slot)
```

The percentile function is using `length` instead of `length - 1`, causing all percentile values to be shifted upward.

### Bounded Ratio Edge Case

Division calculations are failing on edge case:

```
numerator: 100
denominator: 0

Expected: 0.0 (safe default for zero denominator)
Actual: Infinity (division by zero not guarded)
```

The zero check uses `< 0` instead of `<= 0`, so exactly zero slips through.

---

## Compliance Data Issues

### Retention Bucket Classification

Audit records are being misclassified for archival:

| Record Age (days) | Expected Bucket | Actual Bucket |
|-------------------|-----------------|---------------|
| 29                | hot             | hot           |
| 30                | hot             | warm          |
| 364               | warm            | warm          |
| 365               | warm            | cold          |

Records at exactly the boundary (30 days, 365 days) are being prematurely moved to colder storage.

This is causing:
- Increased cold storage read costs when accessing "recent" records
- Compliance issues (some hot queries failing to find expected data)

---

## Security Token Freshness

Authentication logs show occasional false positives for token expiry:

```
Token issued at: 1705910400 (epoch seconds)
Token TTL: 3600 seconds (1 hour)
Current time: 1705914000 seconds (exactly at expiry boundary)

Expected: token IS fresh (1705914000 == 1705910400 + 3600)
Actual: token is EXPIRED
```

Users are being logged out exactly at the TTL boundary when they should still be valid.

---

## Workflow State Mapping

Operations reported workflow state transitions are confusing:

```
Event: "validate"
Expected next state: "validated"
Actual next state: "capacity_checked"

Event: "capacity_ok"
Expected next state: "capacity_checked"
Actual next state: "validated"
```

The state mappings for "validate" and "capacity_ok" appear to be swapped, causing workflow audit trails to show operations happening in the wrong order.

---

## Watermark and Event Processing

Streaming events are being incorrectly rejected:

```
Event timestamp: 1000
Watermark: 1005
Skew tolerance: 5 seconds

Expected: ACCEPT (1000 + 5 = 1005, which equals watermark)
Actual: REJECT (events exactly at tolerance boundary are dropped)
```

---

## Audit Trail Sequence Validation

Audit logs are accepting invalid sequences:

```
Sequence numbers: [1, 2, 2, 3]

Expected: INVALID (contains duplicate at position 2)
Actual: VALID (duplicates not detected)
```

The sequence validation allows consecutive equal values when it should require strictly increasing.

---

## Summary of Issues

| Component | Issue | Business Impact |
|-----------|-------|-----------------|
| SLA breach classification | Off-by-one at all thresholds | Over-reporting breaches by ~2.4% |
| Breach risk detection | False positive at boundary | Unnecessary alerts |
| Percentile calculation | Using length instead of length-1 | All percentiles shifted up |
| Bounded ratio | Zero denominator not caught | Potential division by zero |
| Retention bucketing | Premature tier demotion | Increased storage costs |
| Token freshness | Expiring at exact TTL | User session drops |
| Workflow state mapping | States swapped | Confusing audit trails |
| Watermark acceptance | Rejecting at boundary | Lost events |
| Audit sequence check | Allowing duplicates | Integrity gaps |

---

## Action Items

1. **Engineering**: Audit all comparison operators in SLA, compliance, and statistics modules
2. **Finance**: Recalculate affected period with corrected logic once fixes deployed
3. **Compliance**: Review audit trail integrity with relaxed sequence check

---

## Files to Investigate

Based on symptoms:
- SLA model (breach calculations)
- Statistics reducer (percentile, ratio calculations)
- Compliance ledger (retention bucketing, override validation)
- Security policy (token freshness)
- Workflow orchestrator (state mapping)
- Watermark window (event acceptance)
- Audit trail (sequence validation)

---

**Classification**: Internal - Financial Sensitive
**Next Review**: January 24, 2024
**Escalation**: CFO requesting resolution before monthly close
