# SUPPORT TICKET #QL-4892: SLA Metrics Reporting Incorrect Values

**Priority**: High
**Status**: In Progress
**Requester**: Analytics Team (Sarah Chen)
**Assigned To**: Platform Engineering
**Created**: 2024-03-20 11:15 UTC

---

## Description

Our SLA dashboards are showing metrics that don't match the raw data. The percentile calculations, mean computations, and SLA compliance percentages all appear to be wrong. This is causing confusion with clients during quarterly business reviews.

---

## Reported Issues

### Issue 1: Percentile values are negative

We're getting negative latency percentiles which is impossible:

```
Dashboard shows: P95 latency = -847ms
Raw data P95 should be: ~850ms (all positive values)
```

### Issue 2: Mean latency is underestimated

The mean calculation is consistently lower than expected:

```
Sample data: [100, 200, 300] ms
Expected mean: 200ms
Reported mean: 150ms (seems to be dividing by 4 instead of 3)
```

### Issue 3: SLA compliance at boundary fails

Requests that exactly hit our 120ms target are marked as violations:

```
2024-03-20T10:45:12Z latency_check response_time=120 target=120 sla_met=false
                                                               ^^^^^^^^
                                                               Should be true!
```

### Issue 4: Median calculation crashes on even-length arrays

```
panic: runtime error: index out of range [4] with length 4
    /internal/statistics/latency.go:82
```

---

## Test Failures

```
--- FAIL: TestPercentile
    statistics_test.go:12: unexpected percentile

--- FAIL: TestRollingSLA
    statistics_test.go:18: unexpected sla 0.5000 (expected ~0.75)

--- FAIL: TestMean
    statistics_test.go:26: expected mean 20.0, got 15.0000

--- FAIL: TestMedian
    statistics_test.go:33: expected median 25.0, got NaN
```

---

## Impact

1. **Quarterly Business Reviews**: Cannot present accurate SLA data to 12 enterprise clients
2. **Contractual Risk**: Some clients have SLA credits tied to these metrics
3. **Internal Planning**: Capacity planning uses these metrics for forecasting
4. **Executive Dashboards**: C-suite reviewing incorrect operational metrics

---

## Sample Calculation Trace

```go
// Input latencies in ms
values := []int{90, 120, 80, 140, 110, 95, 130, 115}

// Expected results:
// - Mean: 110ms
// - P95: ~135ms
// - SLA (target=120): 62.5% (5 of 8 under target)

// Actual results from system:
// - Mean: 97.8ms (wrong)
// - P95: -135ms (negative?!)
// - SLA: 50% (wrong)
```

---

## Reproduction Steps

1. Call `statistics.Percentile([]int{10, 20, 30, 40, 50}, 90)`
   - Expected: 50
   - Actual: -50

2. Call `statistics.Mean([]float64{10.0, 20.0, 30.0})`
   - Expected: 20.0
   - Actual: 15.0

3. Call `statistics.RollingSLA([]int{90, 120, 80, 140}, 120)`
   - Expected: 0.75 (3 of 4 meet target)
   - Actual: 0.50

4. Call `statistics.Median([]float64{10.0, 20.0, 30.0, 40.0})`
   - Expected: 25.0
   - Actual: index out of bounds panic

---

## Attachments

- Screenshot of dashboard showing negative P99: `sla_dashboard_negative.png`
- Raw Prometheus metrics export: `metrics_20240320.json`
- Client complaint email from Apex Trading: `apex_complaint.eml`

---

## Comments

**Sarah Chen** (2024-03-20 11:30):
> This is blocking our QBR prep. The CEO of Apex Trading specifically asked about our P99 latency and we showed him -847ms. Very embarrassing.

**Platform Engineering** (2024-03-20 12:15):
> Looking into it. Multiple functions in the statistics module appear to have calculation errors. Will need to review percentile, mean, median, variance, and SLA check logic.

---

## Resolution Required

Fix all statistical calculation functions. Verify with unit tests before deploying.
