# INCIDENT-2024-1903: Catastrophe Response Routing Cost Overruns

**Severity:** P2 - High
**Status:** Open
**Assigned Team:** Claims Logistics Engineering
**Reported:** 2024-11-21 14:22 UTC
**Last Updated:** 2024-11-21 18:45 UTC

---

## Summary

The catastrophe response routing system is consistently selecting suboptimal routes for field adjusters, resulting in significant cost overruns and delayed claim assessments. Analysis shows the corridor selection algorithm is choosing high-latency routes instead of the most efficient options, and cost estimates are systematically lower than actual expenses.

## Business Impact

- **Cost Overrun:** $892,000 above budget for November CAT response operations
- **Delayed Assessments:** Average time-to-site increased by 2.3 hours per claim
- **Adjuster Utilization:** Field adjusters reporting 18% less productive time due to travel
- **Policyholder Complaints:** 47 complaints about delayed adjuster visits

## Symptoms Observed

### 1. Corridor Selection Inversions

When multiple routing corridors are available, the system consistently selects the worst-performing option:

```
Available corridors for Adjuster ADJ-7742 to CLM-991847:
  Corridor A: latency=45min, reliability=0.94
  Corridor B: latency=72min, reliability=0.89
  Corridor C: latency=31min, reliability=0.97  <-- Should be selected

Selected: Corridor B (INCORRECT - highest latency chosen)
```

### 2. Transit Time Underestimation

Field adjusters consistently arrive later than the system predicts:

```
Route: Regional Office -> Claim Site (distance: 156 nautical miles equivalent)
  System estimate: 11.1 hours
  Actual travel time: 13.0 hours

  Note: Default speed assumption appears incorrect
```

### 3. Fuel/Cost Rate Miscalculation

Expense reports show actual costs exceeding estimates by ~10%:

```
Corridor cost estimate: $65.52 (distance: 156nm, rate: 0.42/nm)
Actual expense claim: $59.28 (should be closer to 0.38/nm industry standard)

Note: Current rate appears inflated, but this results in OVER-estimation
      However, combined with routing issues, total costs exceed budget
```

### 4. Multi-Leg Route Distance Errors

Routes with multiple stops show unexpected distance calculations:

```
Leg 1: Office (nm: 0) -> Site A (nm: 50) = 50nm
Leg 2: Site A (nm: 50) -> Site B (nm: 30) = Expected: 20nm backtrack, Actual: 20nm (shows as positive)

The system treats backtracking as positive distance, inflating total route length
```

### 5. Inactive Corridor Inclusion

Routes marked as inactive are still being returned in active route queries:

```
Query: get_active_routes()
Expected: Only corridors with active=true
Actual: Corridors with active=nil also included
```

## Failing Tests

```
RoutingTest#test_choose_lowest_latency_corridor - FAILED
  Expected corridor: C (latency=31)
  Selected corridor: B (latency=72)

RoutingTest#test_transit_time_default_speed - FAILED
  Expected: 13.0 hours (at 12 knots)
  Actual: 11.14 hours (at 14 knots)

ExtendedTest#test_corridor_cost_rate - FAILED
  Expected rate: 0.38
  Actual rate: 0.42

ExtendedTest#test_multileg_backtrack_distance - FAILED
  Expected: negative distance for backtrack
  Actual: positive (absolute) distance

RoutingTest#test_active_routes_excludes_nil - FAILED
  Expected: 3 active routes
  Actual: 5 routes (includes 2 with active=nil)
```

## Affected Components

- `lib/opalcommand/core/routing.rb` - Corridor selection and transit estimation
- `services/gateway/service.rb` - Route node scoring

## Investigation Notes

The corridor selection appears to be using the wrong comparison operator, selecting maximum latency instead of minimum. Additionally, several default values for speed and fuel rates appear to be incorrect.

The multi-leg distance calculation may be incorrectly using absolute values, which would hide backtracking penalties.

## Required Actions

1. Review corridor selection comparison logic
2. Verify default speed and fuel rate constants
3. Examine multi-leg distance calculation for absolute value usage
4. Review active route filtering logic
5. Reconcile November expense reports after fixes deployed

## Contacts

- **Incident Commander:** Robert Kim (Claims Logistics)
- **CAT Response Lead:** Amanda Foster
- **Finance:** Christine Wu (Claims Accounting)

---

*All routing changes require approval from Claims Operations before deployment to production.*
