# Scenario 05: Queue Starvation and SLA Reporting Anomalies

## Incident Type
Customer Escalation / P2 Operations Incident

---

## Customer Escalation Email

**From:** VP Operations, MedLogix Pharma
**To:** Account Executive, PolarisCore
**Subject:** URGENT: Critical shipments being deprioritized

We're experiencing a serious issue with your platform. Our highest-priority shipments (severity 4-5) are consistently being processed LAST instead of first. This is causing SLA breaches for time-sensitive pharmaceutical deliveries.

Additionally, your SLA dashboard is showing 99.8% compliance but our internal tracking shows we're missing SLA on approximately 30% of shipments. Something is very wrong with either the queue ordering or the metrics.

We have a quarterly business review next week and need this resolved immediately.

---

## Internal Investigation Notes

**#support-escalations** Slack Thread

**@support-lead**: Got the MedLogix escalation. Looking at their queue data now.

**@platform-ops**: I pulled the queue ordering for their shipments. Here's what I see:

```
Queue Order (Expected: highest weight first)
============================================
Position 1: id=c, severity=1, waited=800s, weight=36
Position 2: id=a, severity=2, waited=20s,  weight=20
Position 3: id=b, severity=4, waited=10s,  weight=40

Wait... severity 4 item should be FIRST (weight 40), not last!
```

**@support-lead**: The queue is sorted ascending by weight instead of descending. Low priority items are being processed first.

**@platform-ops**: And the pressure metric is off too. The severity coefficient is wrong — getting roughly 2.5x less pressure than expected.

**@analytics-eng**: Found more issues. The percentile calculations are backwards and the SLA calculation has a divisor error:

```
Latencies: [90, 110, 160]
Objective: 120ms

Expected: 2 of 3 within objective → 66.67%
Actual:   divides by (count - 1) instead of count → 2/2 = 100%
```

**@platform-ops**: So we're showing BETTER SLA numbers in dashboards than reality. Customers see 100% compliance when it's really 66.67%. No wonder their internal tracking disagrees with ours.

---

## Dashboard Comparison

```
MedLogix Customer View (their internal tracking):
- P95 Latency: 180ms (they expect 150ms)
- SLA Compliance: 68%
- Avg Wait Time: 847 seconds for priority items

PolarisCore Dashboard (what we show):
- P95 Latency: 45ms (WRONG - inverted percentile)
- SLA Compliance: 99.8% (WRONG - divisor off-by-one inflates result)
- Queue Pressure: 2.1 (should be ~5.3, severity coefficient too low)
```

---

## Business Impact

- **MedLogix account at risk**: $4.2M annual contract
- **6 other enterprise customers** likely experiencing same issues
- **SLA credits**: Estimated $180K in credits owed if confirmed
- **Regulatory exposure**: Pharmaceutical timing requirements not met
- **Dashboard credibility**: Customers losing trust in our reporting

---

## Observed Symptoms

1. Queue ordering is ascending by weight (low priority first, high priority last)
2. Queue pressure severity coefficient too low (0.24 instead of 0.6, ~2.5x undercount)
3. Percentile calculations are inverted (P95 returning low values, P5 returning high)
4. SLA divisor uses `len - 1` instead of `len` (inflates compliance percentage)
5. Trimmed mean divides by original count instead of kept count after trimming

---

## Economic Impact Analysis

```
Cost Projection Analysis
========================
Shipments: 100 units
Lane Cost: $45.00/unit
Surge Multiplier: 2.5x

Expected: 100 * 45.00 * 2.5 = $11,250.00
Actual:   100 * 45.00 + 2.5 = $4,502.50

The surge multiplier is being ADDED instead of MULTIPLIED!
```

**@finance-ops**: This explains the margin anomalies we've been seeing. Projected costs are way too low, actual margins are negative.

---

## Affected Test Files

- `tests/queue_statistics_tests.rs` - Queue ordering, pressure, percentiles, SLA, trimmed mean
- `tests/workflow_integration_tests.rs` - End-to-end queue processing tests

---

## Relevant Modules

- `src/queue.rs` - Queue ordering and pressure calculation
- `src/statistics.rs` - Percentile, SLA, and trimmed mean calculations
- `src/economics.rs` - Cost projection and margin calculations

---

## Investigation Questions

1. What sort order is being used for queue priority?
2. What multiplier is used in the pressure calculation?
3. Is percentile sorting ascending or descending?
4. What divisor is used in rolling SLA (count vs count-1)?
5. What divisor is used in trimmed mean (kept count vs original count)?
6. How is the surge multiplier being applied to cost projections?

---

## Resolution Criteria

- Queue must order by weight descending (highest priority first)
- Pressure calculation must use correct severity coefficient (0.6, not 0.24)
- Percentile must sort ascending and use rank directly (not complement)
- SLA must divide by total count, not count minus one
- Trimmed mean must divide by kept count after trimming, not original count
- Cost projection must multiply by surge (not add)
- Margin calculation boundary must be correct
- All queue, statistics, and economics tests must pass
