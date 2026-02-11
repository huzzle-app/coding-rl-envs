# PagerDuty Incident: Fleet Capacity Exceeded, Vehicles Not Being Shed

## Incident Report INC-20240119-0847

**Severity**: P1 (Critical)
**Triggered**: 2024-01-19 08:47 UTC
**Acknowledged**: 2024-01-19 08:49 UTC
**Resolved**: ONGOING
**Incident Commander**: David Park

---

## Alert Details

```
CRITICAL: Fleet capacity exceeded threshold
Service: transit-dispatch-core
Region: us-west-2
Metric: active_dispatches / fleet_capacity
Value: 1.42 (142% utilization)
Threshold: >= 1.0 for 10 minutes

Secondary Alert: Vehicle shedding not triggering
Expected behavior: Shed at 100% capacity
Actual behavior: Accepting dispatches at 142% capacity
```

---

## Timeline

**08:32 UTC** - Morning rush begins, dispatch volume spikes

**08:40 UTC** - Active dispatches reach 95% of fleet capacity

**08:45 UTC** - Active dispatches hit 100% of fleet capacity
- Expected: Shedding mechanism triggers, oldest dispatches deferred
- Actual: System continues accepting new dispatches

**08:47 UTC** - PagerDuty alert fires at 142% capacity

**08:52 UTC** - Operations reports vehicles "double-booked"
- Same vehicles assigned to overlapping time slots
- ETAs becoming unrealistic (showing vehicle will be in two places at once)

**09:05 UTC** - Fleet capacity at 167%
- Reserve fleet should be maintaining buffer, but being committed

---

## Dashboard Metrics

### Capacity Utilization (08:00 - 09:00 UTC)

```
Time    Active  Capacity  Reserve  Safe-Avail  Shed-Trigger
08:00   450     600       50       550         No
08:15   520     600       50       550         No
08:30   580     600       50       550         No
08:45   602     600       50       ???         No (should be Yes)
09:00   1002    600       50       ???         No (should be Yes)
```

Note: "Safe-Avail" should be `Capacity - Reserve`, but values look wrong

### Shedding Events

```
Expected shedding events since 08:45: 15+
Actual shedding events: 0
```

---

## Operations Team Observations

From control room transcript:

> **Dispatcher Kim (08:48)**: "The board is showing red everywhere but dispatch keeps accepting new orders. Shouldn't the system be throttling?"

> **Supervisor Torres (08:51)**: "We're at 120% and climbing. The shedding flag is stuck at FALSE. I've never seen it this bad."

> **Dispatcher Kim (08:55)**: "Wait, is the reserve calculation inverted? The safe available number is HIGHER than our total fleet. That's impossible."

---

## API Behavior Analysis

### Rebalance Calculation

```json
POST /api/v1/capacity/rebalance

Request:
{
  "availableUnits": 600,
  "queuedDemand": 750,
  "reserveFloor": 50
}

Response:
{
  "allocatedUnits": 650,
  "safeAvailable": 650,
  "reserveViolation": false
}
```

**Problem**: `safeAvailable` should be 550 (600 - 50), but it's returning 650.

This means the system thinks it has MORE capacity than it actually does. The reserve floor is being added instead of subtracted.

### Shedding Check

```json
POST /api/v1/capacity/shed-check

Request:
{
  "inFlight": 600,
  "hardLimit": 600
}

Response:
{
  "shedRequired": false
}
```

**Problem**: When `inFlight == hardLimit`, shedding should trigger, but it doesn't.

---

## Business Requirements

### Capacity Rebalancing
- `safeAvailable = availableUnits - reserveFloor`
- Reserve floor is a buffer that should NEVER be committed
- This prevents overcommitting the fleet

### Shedding Logic
- Shedding MUST trigger when `inFlight >= hardLimit`
- At exactly 600/600, we should start deferring new dispatches
- Current behavior: Only triggers when > 600 (which is too late)

---

## Customer Impact

- **Delayed Dispatches**: 89 dispatches delayed by 30+ minutes
- **Double Bookings**: 12 vehicles assigned conflicting schedules
- **Driver Complaints**: Drivers receiving impossible schedules
- **SLA Impact**: 23 breaches and counting

---

## Mitigation Attempts

1. **Manual throttling**: Dispatchers manually closing intake queues
   - Partial success, but creates backlog

2. **Increased hard limit**: Raised from 600 to 650
   - Made things worse - system now thinks 650 is acceptable

3. **Emergency reserve release**: Released 20 reserve vehicles
   - Didn't help because system was already overcommitting

---

## Technical Notes

The issue appears to be in two places:

1. **Reserve floor calculation**: The math is inverted - we're adding reserve instead of subtracting, making the system think it has more capacity

2. **Shedding threshold**: The comparison is off by one - we're using > instead of >= for the hard limit check

---

## Files to Investigate

- Capacity balancer service
- Queue governor (for related throttling issues)

---

**Next Steps**:
- Engineering to investigate capacity calculation logic
- If fix deployed, monitor for 30 minutes before lifting manual throttle
- Post-incident review scheduled for 2024-01-20 10:00 UTC

**Impact Duration**: 2+ hours and counting
**Estimated Revenue Impact**: $45,000/hour in SLA penalties
