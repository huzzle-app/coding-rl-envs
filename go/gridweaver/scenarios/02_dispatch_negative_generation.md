# Support Ticket: Negative Generation Values in Dispatch Planning

**Ticket ID**: SUP-78234
**Priority**: P2 - High
**Customer**: Western Interconnection Grid Operator (WIGO)
**Product Area**: Dispatch Optimization
**Created**: 2024-03-18 14:22:00 PST

---

## Customer Report

> "Our dispatch planning module is producing negative generation values, which is causing our billing system to interpret this as energy being pulled FROM the grid rather than supplied TO it. We've had three settlement disputes this week because the DispatchPlan.GenerationMW field contains negative numbers. This doesn't make physical sense - you can't generate negative megawatts."

## Reproduction Steps (From Customer)

1. Create a dispatch plan for region "pacific-north" with demand of 500 MW
2. Set reserve percentage to 0.15 (15%)
3. Call `BuildPlan("pacific-north", 500.0, 0.15)`
4. Expected: GenerationMW = 575 (500 + 15% reserve)
5. Actual: GenerationMW = -425 (negative!)

## Internal Investigation

### Symptom 1: BuildPlan Returns Negative Generation

Test output shows consistent negative values:

```
=== Test BuildPlan ===
Input: region=east, demand=1000.0, reservePct=0.10
Expected: GenerationMW >= 1000.0 (at least demand + reserve)
Actual: GenerationMW = -900.0

Input: region=west, demand=500.0, reservePct=0.20
Expected: GenerationMW >= 500.0
Actual: GenerationMW = -400.0
```

Pattern: The result appears to be `reserve - demand` instead of `demand + reserve`.

### Symptom 2: RoundGeneration Returns Negative Values

Even when starting with positive MW values, the rounding function inverts them:

```
=== Test RoundGeneration ===
Input: mw=123.456, precision=2
Expected: 123.45 or 123.46 (rounded)
Actual: -123.45

Input: mw=1000.0, precision=0
Expected: 1000.0
Actual: -1000.0
```

### Symptom 3: Capacity Margin Inverted

The capacity margin calculation shows negative margins when there's actually surplus generation:

```
=== Test CapacityMargin ===
Input: generation=1200.0, demand=1000.0
Expected: 0.20 (20% positive margin - surplus)
Actual: -0.20 (appears as deficit)

Input: generation=800.0, demand=1000.0
Expected: -0.20 (20% negative margin - deficit)
Actual: 0.20 (appears as surplus)
```

### Symptom 4: Merit Order Sorted Backwards

Dispatch priority should order generators from cheapest to most expensive (economic dispatch), but the ordering is reversed:

```
=== Test MeritOrder ===
Units: [
  {ID: "solar-1", CostPerMW: 15.00},
  {ID: "gas-1", CostPerMW: 45.00},
  {ID: "coal-1", CostPerMW: 35.00}
]
Expected Order: ["solar-1", "coal-1", "gas-1"] (cheapest first)
Actual Order: ["gas-1", "coal-1", "solar-1"] (most expensive first!)
```

This causes expensive peaker plants to dispatch before baseload, increasing customer costs by ~$2.3M/day.

### Symptom 5: Ramp Constraints Rejecting Valid Transitions

Valid ramp transitions that are exactly at the limit are being rejected:

```
=== Test ValidateRampConstraint ===
Input: current=100.0, target=150.0, maxRamp=50.0
Delta: 50.0 (exactly at limit)
Expected: true (valid - within constraint)
Actual: false (rejected)
```

### Symptom 6: Split Dispatch Producing Insufficient Total

When splitting 1000 MW across 4 units, the total assigned is less than required:

```
=== Test SplitDispatch ===
Input: totalMW=1000.0, units=4
Expected per unit: 250.0 (1000/4)
Actual per unit: 200.0 (appears to divide by 5 instead of 4)
Total assigned: 800.0 (missing 200 MW!)
```

### Symptom 7: Weighted Dispatch Ignoring Weights

The weighted dispatch function produces equal distribution regardless of weights:

```
=== Test WeightedDispatch ===
Demands: [100.0, 200.0, 300.0]
Weights: [0.5, 0.3, 0.2]  (should favor first demand)
Expected: proportional to weights
Actual: [200.0, 200.0, 200.0] (equal distribution, weights ignored)
```

### Symptom 8: Total Generation Truncated

When summing dispatch plans, fractional MW values are being lost:

```
=== Test TotalGeneration ===
Plans: [
  {GenerationMW: 100.7},
  {GenerationMW: 200.3},
  {GenerationMW: 50.9}
]
Expected: 351.9
Actual: 350.0 (lost 1.9 MW to truncation)
```

Over 1000 plans, this truncation error compounds to significant discrepancies.

## Business Impact

- Settlement disputes: 3 active, ~$1.2M at risk
- Peaker over-dispatch: Estimated $2.3M/day excess fuel cost
- Ramp rejection: Delayed response to demand changes
- Missing capacity: 200 MW shortfall per dispatch cycle

## Files to Investigate

- `internal/dispatch/solver.go` - Dispatch planning and optimization
- Focus on mathematical operations and sort orderings

## Customer Workaround

Customer is manually post-processing dispatch outputs to flip negative values, but this masks the underlying issue and doesn't fix the merit order or rounding problems.

---

**Assigned To**: Grid Platform Engineering
**Due Date**: 2024-03-20 (URGENT - settlement deadline)
