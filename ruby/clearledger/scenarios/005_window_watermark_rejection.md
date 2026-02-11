# Customer Escalation: Ledger Events Rejected Despite Valid Timestamps

**Ticket ID**: SUP-2024-8834
**Customer**: Meridian Capital Partners
**Priority**: P3 - Medium
**Status**: Engineering Review
**Created**: 2024-01-16 11:30 UTC

---

## Customer Report

> We're experiencing intermittent rejections of ledger events that should be within acceptable time windows. Our trading system is sending events with timestamps that are definitely within the watermark tolerance, but ClearLedger is rejecting them as "outside window bounds."
>
> This is causing settlement delays and we're at risk of missing our T+1 obligations.

---

## Technical Investigation

### Issue 1: Event Window Bounds Check

The `event_in_window?` function appears to have incorrect boundary logic:

```ruby
# Window: 1000 to 2000
# Event timestamp: 1500 (clearly inside window)

LedgerWindow.event_in_window?(1500, 1000, 2000)
# Expected: true
# Actual: false
```

Events at the start of a window (e.g., timestamp 1000 in window 1000-2000) are also being rejected.

### Issue 2: Percentile Calculation Edge Cases

Customer's latency percentile calculations are off at boundaries:

```ruby
latencies = [10, 20, 30, 40, 50]
Routing.route_latency_percentile(latencies, 0.0)
# Expected: 10 (0th percentile = minimum)
# Actual: 20 (off by one index)
```

This is causing their latency SLA reports to show inflated values.

### Issue 3: Queue Drain Batch Size

Batch processing is draining one extra item per batch:

```ruby
queue = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
QueuePolicy.drain_batch(queue, 3)
# Expected: [1, 2, 3] (first 3 items)
# Actual: [1, 2, 3, 4] (4 items!)
```

This is causing batch size limit violations and downstream throttling.

### Issue 4: Statistics Median Calculation

For even-length arrays, the median calculation is incorrect:

```ruby
Statistics.median([1, 2, 3, 4])
# Expected: 2.5 (average of 2 and 3)
# Actual: 3 (just taking middle-right element)
```

This is affecting their settlement amount median reports.

### Issue 5: Failover Candidate Selection Inverted

When a node partition occurs, the system selects degraded nodes instead of healthy ones:

```ruby
nodes = ['node-a', 'node-b', 'node-c']
degraded = ['node-b']

Resilience.failover_candidates(nodes, degraded)
# Expected: ['node-a', 'node-c'] (healthy nodes)
# Actual: ['node-b'] (degraded node!)
```

This is routing traffic TO failed nodes instead of AWAY from them.

### Issue 6: Weighted Latency Missing Normalization

The weighted latency calculation doesn't normalize by total weight:

```ruby
routes = [
  { latency: 100, weight: 0.5 },
  { latency: 200, weight: 0.5 }
]
Routing.weighted_latency(routes)
# Expected: 150 (weighted average)
# Actual: 150 (happens to work here, but...)

routes = [
  { latency: 100, weight: 1.0 },
  { latency: 200, weight: 1.0 }
]
Routing.weighted_latency(routes)
# Expected: 150 (weighted average)
# Actual: 300 (just sum, not average)
```

---

## Affected Customer Workflows

1. **Real-time event ingestion**: ~15% of valid events rejected
2. **Latency percentile reporting**: P99 values inflated by ~20%
3. **Batch settlement processing**: Batches oversized, triggering rate limits
4. **Median settlement reporting**: Statistical reports inaccurate
5. **Failover routing**: Traffic misrouted during node failures

## Customer Impact

- 847 events rejected in last 24 hours (should be 0)
- Settlement batch processing delayed by 45 minutes average
- Failover test last week routed 100% traffic to degraded node
- SLA compliance reports showing false violations

## Engineering Notes

These issues suggest:
1. Off-by-one errors in index calculations and boundary checks
2. Inverted filter/selection logic in failover
3. Missing averaging step in weighted calculations
4. Incorrect comparison operators in window boundary checks

## Resolution Criteria

- [ ] `event_in_window?` correctly returns true for events within [start, end)
- [ ] `route_latency_percentile` returns correct percentile value
- [ ] `drain_batch` returns exactly `batch_size` items
- [ ] `median` returns correct median for both odd and even length arrays
- [ ] `failover_candidates` returns non-degraded nodes
- [ ] `weighted_latency` returns weighted average (divide by sum of weights)

## Timeline

- Customer expecting update by EOD 2024-01-16
- T+1 settlement deadline: 2024-01-17 09:00 UTC
- Escalation to VP if not resolved by 2024-01-16 18:00 UTC
