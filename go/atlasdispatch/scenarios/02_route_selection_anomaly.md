# Support Ticket: Route Selection Choosing Worst Available Routes

**Ticket ID:** SUP-77291
**Priority:** P2 - High
**Category:** Routing Engine
**Submitted By:** James Okonkwo, Fleet Optimization Lead
**Date:** 2024-11-12

---

## Problem Description

The route selection algorithm is consistently choosing the highest-latency routes instead of optimal ones. This is causing fleet-wide delays and increased fuel costs.

## Environment

- Production cluster: atlas-prod-east
- Affected channels: PACIFIC_MAIN, ATLANTIC_EXPRESS, SUEZ_PRIORITY
- Data timestamp: 2024-11-12 14:00-18:00 UTC

## Detailed Symptoms

### Route Selection (ChooseRoute)

When presented with multiple valid routes, the system selects the route with the HIGHEST latency:

```
Available Routes:
- PACIFIC_MAIN:    latency=120ms, blocked=false
- PACIFIC_ALT:     latency=450ms, blocked=false
- PACIFIC_BACKUP:  latency=890ms, blocked=false

Expected Selection: PACIFIC_MAIN (lowest latency)
Actual Selection:   PACIFIC_BACKUP (highest latency)
```

### Channel Scoring (ChannelScore)

The scoring function produces counterintuitive results. Routes with poor characteristics score higher:

```
Route A: latency=50, reliability=0.99, priority=1
Route B: latency=500, reliability=0.50, priority=9

Expected: Route A should score higher (low latency, high reliability)
Actual: Route B scores significantly higher
```

### Route Comparison

When sorting routes for display or selection, the comparison function appears inverted:

```
Comparing Route A (latency=100) vs Route B (latency=200)
Expected: A should come before B (A < B, return negative)
Actual: A comes after B (comparison returns positive for A < B)
```

### Multi-Leg Planning

The `MultiLegPlan` response is missing the leg count field. Consumers relying on this field receive 0 regardless of actual legs:

```json
{
  "legs": [{"channel": "A", "latency": 10}, {"channel": "B", "latency": 20}],
  "totalDelay": 30,
  "legCount": 0  // Should be 2
}
```

### Transit Time Estimation

When tested with edge cases, transit time calculations return invalid results:

```
Input: distanceKm=-50, speedKnots=20
Expected: Error or 0 (negative distance is invalid)
Actual: Returns negative transit time (-1.35 hours)
```

### Route Cost Estimation

The delay surcharge component seems underweighted:

```
Input: latency=100, fuelRate=2.5, distanceKm=1000
Expected cost calculation: (2.5 * 1000) + (100 * 0.5) = 2550
Actual cost:               (2.5 * 1000) + (100 * 0.3) = 2530

The 0.3 coefficient doesn't match our published rate card (0.5/ms delay)
```

## Business Impact

- Average route latency increased 340% over baseline
- Fuel consumption up 28% due to suboptimal routing
- Delivery windows missed for 156 shipments
- Customer complaints up 4x from routing-related delays

## Reproduction Steps

1. Create a RouteTable with 3+ routes of varying latency
2. Mark none as blocked
3. Call ChooseRoute with empty blocked map
4. Observe that highest-latency route is selected

## Attachments

- route_selection_logs_20241112.json
- latency_comparison_analysis.xlsx
- customer_complaints_routing.csv

## Requested Resolution

Please investigate the sorting and comparison logic in the routing module. The behavior suggests inverted sort order or comparison operators.

---

**Assigned To:** Routing Team
**SLA Target:** 48 hours
**Last Updated:** 2024-11-12 18:45 UTC
