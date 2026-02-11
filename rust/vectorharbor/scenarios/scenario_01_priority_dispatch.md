# Scenario 01: Priority Dispatch Inversion

## Type: Incident Report

## Severity: P1 - Critical

## Date: 2024-12-15 03:42 UTC

---

### Summary

High-priority vessels are being systematically deprioritized during peak congestion, resulting in SLA breaches for critical cargo.

### Timeline

- **03:42** - NOC receives alert: 4 critical-severity vessels missed their 15-minute SLA window
- **03:47** - Initial investigation shows vessels were queued correctly with severity=5
- **03:55** - Dispatcher reports: "Low-priority maintenance vessels allocated berths before hazmat tankers"
- **04:12** - Port authority escalates: critical medical supply shipment delayed by 2 hours
- **04:30** - Incident declared; manual intervention begins

### Observed Behavior

When the dispatch system processes a batch of mixed-priority orders under capacity constraints:

1. Orders with **lower** urgency scores are processed **before** orders with higher urgency
2. Cost estimation for time-critical shipments (SLA <= 15 min) appears underestimated
3. Urgency scores for dispatch orders seem inverted - shorter SLA results in lower scores

### Expected Behavior

1. High-urgency orders should be allocated first when capacity is limited
2. Orders with severity=5 and tight SLA should have the highest urgency scores
3. Cost estimates should properly factor in both severity and time pressure

### Reproduction Steps

```
1. Create dispatch batch with:
   - Order A: severity=5, sla_minutes=10
   - Order B: severity=2, sla_minutes=180
   - Order C: severity=4, sla_minutes=15

2. Call dispatch_batch with capacity=1

3. Expected: Order A allocated (highest urgency)
   Actual: Order B allocated (lowest urgency)
```

### Business Impact

- 12 SLA breaches in 6-hour period
- $240,000 in penalty clauses triggered
- Port authority review scheduled

### Affected Systems

- `src/allocator.rs` - dispatch planning and order allocation
- `src/models.rs` - urgency score calculation

### Metrics

```
allocation_priority_violations: 847
sla_breach_critical_severity: 12
cost_estimation_underflow_count: 156
```

### Notes from On-Call

"The sorting looks correct at first glance but the results are backwards. Also noticed that orders with exactly 15-minute SLA aren't getting the 3x urgency factor - they're falling through to 2x."

---

**Status**: Investigating
**Assigned**: Platform Team
**Related Tickets**: DISP-4421, DISP-4423, DISP-4425
