# Operations Escalation: Dispatches Consistently Taking Longest Routes

## JIRA Ticket OPS-4821

**Priority**: Critical
**Reporter**: Maria Chen, Regional Operations Manager
**Created**: 2024-01-18 09:15 PST
**Status**: Escalated to Engineering

---

## Issue Summary

Our dispatch center has been experiencing a significant increase in late arrivals and SLA violations over the past 72 hours. Upon investigation, we've discovered that TransitCore is consistently selecting the longest possible routes for dispatches, even when faster alternatives are clearly available.

## Impact Assessment

- **SLA Breaches**: 47 SLA violations in the past 24 hours (normal is 2-3)
- **Revenue Impact**: Estimated $180,000 in penalty fees
- **Customer Complaints**: 23 escalated customer tickets about late arrivals
- **Driver Complaints**: Multiple reports of "system sending me the long way around"

---

## Observed Behavior

### Example 1: Downtown to Airport Route

Dispatch #D-20240118-0732:
- **Origin**: Downtown Transit Hub (DTH)
- **Destination**: Regional Airport (APT)
- **Available Routes**:
  | Route | Estimated Time |
  |-------|----------------|
  | Express Highway | 18 minutes |
  | Surface Streets | 35 minutes |
  | Scenic Route | 52 minutes |
- **Route Selected by System**: Scenic Route (52 minutes)
- **Actual Result**: 58 minutes (6 minutes over estimate due to traffic)
- **SLA Target**: 30 minutes
- **Breach**: +28 minutes

### Example 2: Industrial Zone to Port

Dispatch #D-20240118-1145:
- **Origin**: Industrial Hub East (IHE)
- **Destination**: Cargo Port Terminal (CPT)
- **Available Routes**:
  | Route | Estimated Time |
  |-------|----------------|
  | Freight Corridor | 22 minutes |
  | Highway Loop | 41 minutes |
- **Route Selected by System**: Highway Loop (41 minutes)
- **SLA Target**: 35 minutes
- **Breach**: +6 minutes

---

## Dispatcher Observations

From shift supervisor log (01/18 morning shift):

> "Every single dispatch this morning has been assigned to what looks like the worst possible route. When I manually override and select a faster route, the delivery completes on time. But the system keeps picking the longest option."

> "I ran a test dispatch from Station A to Station B. There are three routes: 12 min, 24 min, and 38 min. The system picked 38 min. Every. Single. Time."

---

## API Response Analysis

Sample API call to route selection endpoint:

```json
POST /api/v1/dispatch/route-selection

Request:
{
  "origin": "DTH",
  "destination": "APT",
  "travelMinutesByRoute": {
    "express_highway": 18,
    "surface_streets": 35,
    "scenic_route": 52
  }
}

Response:
{
  "selectedRoute": "scenic_route",
  "estimatedMinutes": 52,
  "selectionReason": "optimal"
}
```

The system is returning `"selectionReason": "optimal"` but selecting the 52-minute route over the 18-minute route.

---

## Additional Data Points

1. **Priority Assignment**: High-priority dispatches are getting appropriate priority scores (90+), but then being assigned to the worst routes anyway

2. **Hub Selection**: The routing hub selection also seems off - we're seeing dispatches routed through our most congested hubs instead of the clear ones

3. **Pattern**: This is happening 100% of the time, not intermittently

4. **Rollback Attempt**: We tried reverting to the previous config, but the behavior persists - this appears to be in the core routing logic

---

## Business Requirements

For route selection:
- System MUST select the fastest available route
- In case of tie, prefer alphabetically first route (for consistency)

---

## Workarounds Currently in Place

1. Dispatchers are manually overriding all route selections
2. This is adding 3-5 minutes per dispatch for manual review
3. Cannot scale - we need automated routing to work correctly

---

## Files to Investigate

Based on the API tracing:
- Route selection logic in dispatch planner
- Hub selection algorithm in routing heuristics

---

**Assigned**: @platform-engineering
**Deadline**: ASAP - SLA penalties accumulating hourly
**Customer Escalation**: Yes - Enterprise customers threatening contract review
