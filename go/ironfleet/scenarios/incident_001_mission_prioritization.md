# Incident Report: INC-2024-0871

**Severity:** P1 - Critical
**Status:** Open
**Reported:** 2024-03-15 14:32 UTC
**Service:** IronFleet Mission Allocator
**Region:** CENTCOM Theater Operations

---

## Executive Summary

Critical mission dispatch failures observed during high-tempo operations. Low-priority resupply convoys are being dispatched ahead of high-urgency medical evacuation and ammunition resupply missions, causing significant operational impact.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 13:45 | Mission queue begins backing up with mixed-urgency orders |
| 14:02 | Field commanders report MEDEVAC convoy still queued despite Urgency-7 classification |
| 14:15 | Routine supply convoy (Urgency-2) departs Depot Alpha instead of waiting MEDEVAC |
| 14:28 | Escalation to Fleet Operations Center |
| 14:32 | Incident declared |

---

## Symptoms

1. **Inverted Priority Selection**: When multiple dispatch orders are queued, the allocator consistently selects lower-urgency missions over higher-urgency ones.

2. **Test Failures Observed**:
   ```
   === FAIL: TestPlanDispatchRespectsCapacity
       core_test.go:21: unexpected dispatch ordering: [{ID:a Urgency:1 ETA:09:30} {ID:b Urgency:3 ETA:10:00}]
   ```

   ```
   === FAIL: TestHyperMatrix/case_00042
       hyper_matrix_test.go:40: urgency ordering violated: [{ID:c-42 Urgency:4 ETA:...} {ID:b-42 Urgency:196 ETA:...}]
   ```

3. **Operational Logs** (from `fleet-allocator` pod):
   ```
   2024-03-15T14:02:11Z INFO  PlanDispatch called orders=5 capacity=2
   2024-03-15T14:02:11Z DEBUG sorted_order=["ORD-2241(urgency=1)", "ORD-2238(urgency=3)", "ORD-2239(urgency=5)", "ORD-2240(urgency=7)", "ORD-2237(urgency=2)"]
   2024-03-15T14:02:11Z INFO  dispatching=["ORD-2241", "ORD-2238"]
   ```
   Note: The sorted order shows ascending urgency values when it should be descending.

---

## Impact

- **Operational**: 3 MEDEVAC missions delayed by average 47 minutes
- **Safety**: Increased risk to personnel awaiting medical evacuation
- **Compliance**: Violation of MISSIONPRI-7 doctrine requiring highest-urgency-first dispatch

---

## Affected Components

- `internal/allocator/allocator.go` - PlanDispatch function
- All downstream consumers of dispatch ordering

---

## Metrics Snapshot

```
ironfleet_dispatch_priority_inversions_total{theater="centcom"} 47
ironfleet_medevac_queue_wait_seconds{p99} 2847
ironfleet_dispatch_ordering_violations_total 156
```

---

## Investigation Notes

The dispatch planner is supposed to sort orders by urgency in descending order (highest urgency first), with ETA as a tiebreaker. Current behavior suggests the sort comparator may be inverted.

Related test: `TestPlanDispatchRespectsCapacity` expects orders sorted `[c(urgency=3), b(urgency=3)]` but receives them in wrong order.

---

## Rollback Considered

Previous version (v2.3.1) did not exhibit this behavior. Root cause analysis needed before deploying fix.

---

## Action Items

- [ ] Identify root cause in dispatch sorting logic
- [ ] Verify fix against unit and stress test suites
- [ ] Validate deterministic ordering for equal-urgency cases
