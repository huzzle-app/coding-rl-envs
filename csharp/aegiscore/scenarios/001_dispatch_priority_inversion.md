# INC-2847: Critical Dispatch Orders Being Delayed Behind Low-Priority Cargo

**Severity**: P1 - Critical
**Service**: AegisCore Dispatch Planner
**Reported by**: Port Operations Manager, Rotterdam Terminal
**Date**: 2024-11-15 09:23 UTC

---

## Incident Summary

Multiple critical cargo dispatches are experiencing unexpected delays. High-urgency orders (severity 4-5) with tight SLA windows are being processed AFTER routine low-priority orders (severity 1-2), causing SLA breaches and berth congestion.

## Timeline

- **08:45 UTC**: Night shift handover; dispatch queue contained 47 pending orders
- **08:52 UTC**: Automated planner runs batch allocation for berth capacity of 15
- **08:55 UTC**: Operations notices emergency hazmat vessel (urgency=5, SLA=15min) still queued
- **09:10 UTC**: First SLA breach alert fires for order `ORD-8842` (critical medical supplies)
- **09:15 UTC**: Manual override required; 3 vessels had to be re-routed

## Observed Behavior

When running the dispatch planner with a batch of orders:
- Low-urgency orders (urgency=1, SLA=240min) are being selected for dispatch
- High-urgency orders (urgency=5, SLA=15min) remain in the rejected queue
- The planner appears to be sorting orders in the WRONG direction

## Business Impact

- 3 SLA breaches in 90 minutes (normally 0-1 per week)
- Emergency hazmat cargo delayed by 47 minutes
- Estimated financial impact: $340,000 in demurrage fees
- Compliance risk: SOLAS regulations require priority for hazmat cargo

## Reproduction Steps

1. Submit a batch with mixed urgency levels
2. Set capacity lower than total order count
3. Observe which orders are selected vs rejected

## Relevant Test Failures

The following tests are failing in the test suite:

```
PlanDispatchRespectsCapacity
DispatchBatchSplitsCorrectly
```

The tests expect high-urgency orders to be prioritized, but they are being deprioritized.

## System Context

- Allocator module handles dispatch planning
- `PlanDispatch` method sorts and selects orders by urgency
- Capacity is constrained by available berth slots

## Notes from On-Call Engineer

> "Looked at the logs and the sort seems inverted. Orders with Urgency=1 are at the top of the planned list. Pretty sure we want high urgency first, not low urgency first." - @chen.maritime

---

**Status**: Open
**Assigned Team**: Core Platform
**Related Bugs**: AGS0001
