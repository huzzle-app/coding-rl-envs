# INC-2024-0847: Critical Cargo Delayed While Low-Priority Vessels Serviced First

## Incident Summary

**Severity**: P1 - Critical
**Status**: Open
**Reported**: 2024-11-14 03:42 UTC
**Service**: ChronoMesh Dispatch Allocator
**Impact**: $2.3M perishable cargo at risk, 3 critical medical supply vessels delayed

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 02:15 | Port Rotterdam receives 47 dispatch requests in 15-minute window |
| 02:18 | Dispatch planner processes batch, assigns berth slots |
| 02:45 | Harbor master notices bulk grain vessels assigned before medical supply vessel |
| 03:12 | Cold chain sensors on Vessel MV-ARCTIC-FROST show temperature rising |
| 03:42 | Incident declared after second critical cargo missed optimal offload window |

---

## Symptoms Observed

### 1. Priority Inversion in Dispatch Queue

Operations team observed that when running `plan_dispatch()` with mixed urgency orders:
- Vessels with urgency=1 (lowest) consistently scheduled before urgency=5 (highest)
- The dispatch order appears inverted from expected behavior
- Same ETA vessels should tie-break correctly, but urgency ordering is completely backwards

**Example from logs:**
```
Input orders:
  - ORD-4401: urgency=5, eta=08:00 (CRITICAL - medical supplies)
  - ORD-4402: urgency=2, eta=08:00 (LOW - bulk grain)
  - ORD-4403: urgency=4, eta=09:00 (HIGH - refrigerated produce)

Actual dispatch sequence: ORD-4402, ORD-4403, ORD-4401
Expected dispatch sequence: ORD-4401, ORD-4403, ORD-4402
```

### 2. Berth Slot Conflicts Blocking Adjacent Assignments

Separately, berth scheduling is rejecting valid slot assignments:
- Slot A ends at 14:00, Slot B starts at 14:00
- System reports conflict when these should be adjacent (non-overlapping)
- Operations had to manually override 12 assignments overnight

**Conflict detection output:**
```
Existing slot: berth-7, 10:00-14:00, occupied=true
New request: berth-7, 14:00-18:00
Result: CONFLICT (expected: NO CONFLICT)
```

### 3. Cost Estimates Showing Negative Values

Finance flagged that some voyage cost estimates are negative:
- `estimate_cost(distance=250, rate=1.2, base_fee=50)` returns `250`
- Expected: `250 * 1.2 + 50 = 350`
- Actual: `250 * 1.2 - 50 = 250`

This is causing billing reconciliation failures downstream.

### 4. Capacity Check Allowing Overload

Terminal capacity monitoring shows:
- Max capacity set to 100 units
- `check_capacity(100, 100)` returns `true` (allows loading)
- When load reaches exactly max, system should reject new cargo
- Result: Terminal exceeded safe capacity limits twice this week

---

## Business Impact

- 3 critical medical supply deliveries delayed 4+ hours
- $2.3M perishable cargo at elevated spoilage risk
- 14 bulk cargo vessels processed ahead of priority freight
- Port authority reviewing our SLA compliance

---

## Technical Notes

Relevant code paths:
- `src/allocator.cpp`: `plan_dispatch()`, `has_conflict()`, `estimate_cost()`, `check_capacity()`
- Sorting comparator logic for urgency ordering
- Slot overlap detection boundary conditions
- Cost calculation arithmetic
- Capacity boundary comparison operators

---

## Action Required

Investigate the dispatch planning logic to identify why:
1. High-urgency orders are being scheduled last instead of first
2. Adjacent (non-overlapping) berth slots trigger false conflicts
3. Base fees are being subtracted instead of added to costs
4. Capacity checks allow load to reach (not exceed) max instead of staying below
