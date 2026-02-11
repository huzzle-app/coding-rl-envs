# Scenario 005: Monitoring Dashboard Shows Impossible Metrics

## Type: Support Ticket

## Ticket ID: SUPPORT-8834

## Priority: Medium

## Customer: Port of Singapore Operations Team

---

## Issue Description

Our SignalDock monitoring dashboard is displaying metrics that don't match reality. The numbers are consistently wrong in ways that make capacity planning impossible.

---

## Specific Discrepancies

### 1. Queue Size Always Shows +1

**Dashboard shows:** Queue depth = 101
**Actual items in queue:** 100

**Dashboard shows:** Queue depth = 1
**Actual items in queue:** 0 (empty queue)

Every queue size metric is exactly 1 higher than the actual count. This is causing false alerts when we approach capacity limits.

### 2. Average Response Time Too Low

We're measuring response times manually for a sample of 100 dispatch operations:

| Metric | Dashboard Value | Manual Calculation |
|--------|----------------|-------------------|
| Mean response time | 180ms | 200ms |
| Sample size | 100 | 100 |

The dashboard mean is consistently ~10% lower than reality. We suspect the averaging formula is dividing by the wrong number.

### 3. P95 Latency Completely Wrong

Our SLA requires P95 response time under 500ms. Dashboard shows we're meeting this, but customer complaints suggest otherwise.

**Dashboard P95:** 420ms
**Expected P95 (from raw data):** 680ms

The P95 values seem inverted somehow - like it's showing the 5th percentile instead of the 95th.

### 4. Utilization Never Reaches 100%

Our rolling window scheduler shows maximum utilization of ~91% even when windows are completely full.

**Window capacity:** 10 vessels
**Vessels scheduled:** 10
**Displayed utilization:** 91%

Expected utilization should be 100% when the window is full.

### 5. Wait Time Estimates Off By One

Estimated wait time for queue position 0 should be near-instant, but shows a non-zero value.

**Queue position:** 0 (front of queue)
**Processing rate:** 10/second
**Displayed wait time:** 0.1 seconds (should be ~0)

---

## Business Impact

- SLA reporting is inaccurate
- Capacity planning decisions based on wrong data
- False positive alerts wasting operator time
- Customer trust issues when our metrics don't match their observations

---

## Files to Investigate

Based on the symptoms:
- `src/core/queue.js` - Queue size reporting
- `src/core/statistics.js` - Mean, percentile calculations
- `src/core/scheduling.js` - Utilization calculations

---

## Requested Actions

1. Audit all metric calculation functions for off-by-one errors
2. Verify sort order in percentile calculations (ascending vs descending)
3. Check divisor formulas in averaging functions
