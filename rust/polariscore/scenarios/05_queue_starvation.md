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

**@platform-ops**: And the pressure metric is way off too. Expected ~27.2, getting ~2.7. It's 10x too low.

**@analytics-eng**: Found more issues. The percentile calculations are backwards and the SLA calculation has an off-by-one at the boundary:

```
Latencies: [90, 110, 160]
Objective: 120ms

Expected: 110 is at boundary, should count as within SLA
Expected SLA: 66.67% (2 of 3 within)
Actual SLA: 33.33% (only counting strictly less than)
```

**@platform-ops**: So customers are seeing WORSE SLA numbers in their dashboards than reality, while we're showing BETTER numbers. No wonder they're confused.

---

## Dashboard Comparison

```
MedLogix Customer View (their internal tracking):
- P95 Latency: 180ms (they expect 150ms)
- SLA Compliance: 68%
- Avg Wait Time: 847 seconds for priority items

PolarisCore Dashboard (what we show):
- P95 Latency: 45ms (WRONG - inverted percentile)
- SLA Compliance: 99.8% (WRONG - boundary not counted)
- Queue Pressure: 2.7 (should be ~27)
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
2. Queue pressure calculation is 10x lower than expected
3. Percentile calculations are inverted (P95 returning low values, P5 returning high)
4. SLA boundary using `<` instead of `<=` (latency exactly at objective not counted)
5. Trimmed mean calculations are slightly off due to divisor error

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
4. What comparison operator is used for SLA boundary?
5. What divisor is used in trimmed mean?
6. How is the surge multiplier being applied to cost projections?

---

## Resolution Criteria

- Queue must order by weight descending (highest priority first)
- Pressure calculation must use correct multiplier
- Percentile must sort ascending (low to high)
- SLA must count values at or below objective (`<=`)
- Trimmed mean must divide by actual kept count
- Cost projection must multiply by surge (not add)
- Margin calculation boundary must be correct
- All queue, statistics, and economics tests must pass
