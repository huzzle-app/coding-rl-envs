# Scenario 004: Vessel Routing Optimization Producing Suboptimal Paths

## JIRA Ticket: MERC-4521

**Type:** Bug
**Priority:** High
**Component:** Routing Engine, Channel Scoring
**Labels:** `optimization`, `cost-overrun`, `customer-escalation`
**Sprint:** 2024-Q4-Sprint-8

---

### Description

Multiple shipping partners have reported that MercuryLedger's routing recommendations are consistently suboptimal. Vessels are being routed through high-latency corridors despite reliable low-latency alternatives being available. Cost estimates are also significantly undervaluing hazmat cargo routes.

This has resulted in:
- 23% increase in average transit times vs manual planning
- $847K in unexpected fuel surcharges (November)
- 3 major accounts threatening to switch to CompetitorX

---

### Steps to Reproduce

1. Create a route request with 5 corridor options of varying latency/reliability
2. Observe that the selected corridor prioritizes latency incorrectly
3. Compute channel health score for a corridor with latency=100ms, reliability=0.95
4. Expected score should heavily weight reliability (70%), but actual weights appear inverted

---

### Expected vs Actual Behavior

**Channel Health Scoring:**
```ruby
# Corridor: latency=100ms, reliability=0.95
# Expected: Score should be ~0.72 (reliability-dominant)
# Actual: Score is ~0.38 (latency-dominant)
```

The weights appear to be inverted - latency is getting 70% weight when reliability should.

**Corridor Cost Estimation:**
```ruby
# Hazmat corridor: base_cost=10000, distance=500nm
# Expected: $10000 * 1.15 (hazmat surcharge) = $11500
# Actual: $10000 (no surcharge applied)
```

Hazmat vessels are being quoted the same rate as standard cargo, leading to cost overruns.

**Multi-Leg Planning:**
```ruby
# Route with 3 legs
# Expected result should include: { leg_count: 3, ... }
# Actual result: leg_count field missing
```

Downstream analytics cannot properly attribute costs per leg.

---

### Weather Factor Calculation

Operations team noticed that weather-adjusted ETAs are incorrect:

```ruby
# Base transit: 10 hours
# Weather factor: 1.2 (20% delay expected)
# Expected ETA: 10 * 1.2 = 12 hours
# Actual: Appears to be adding instead of multiplying
```

Vessels are arriving later than estimated during storm season.

---

### Risk Aggregation Issue

Route risk scoring for multi-leg journeys is inflated:

```ruby
# 4 legs with risks: [0.1, 0.2, 0.15, 0.25]
# Expected: Average risk = 0.175
# Actual: Returns sum = 0.70
```

This causes the system to reject safe routes as "high risk."

---

### Gateway Node Selection

Related issue in the gateway service - node selection appears inverted:

```ruby
# Nodes sorted by score, but picking worst instead of best
# Node A: score=0.95 (healthy, low latency)
# Node B: score=0.42 (degraded)
# Expected selection: Node A
# Actual selection: Node B
```

Traffic is being routed to degraded nodes.

---

### Failing Tests

```
FAILED: test_channel_health_score_weights
  Expected reliability weight: 0.7
  Actual reliability weight: 0.3

FAILED: test_corridor_cost_hazmat_surcharge
  Expected: base * 1.15
  Actual: base (no surcharge)

FAILED: test_multi_leg_plan_includes_leg_count
  Expected key :leg_count in result
  Actual: key missing

FAILED: test_weather_factor_multiplication
  Expected: base * weather_factor
  Actual: appears to use different formula

FAILED: test_route_risk_average
  Expected: sum / count (average)
  Actual: raw sum

FAILED: test_select_primary_node_best_score
  Expected: highest scored node
  Actual: lowest scored node
```

---

### Customer Impact Statement

> "We've been using MercuryLedger for our Pacific routes for 2 years. Since the last update, our fuel costs have increased 18% and transit times are up 12%. Our logistics team is spending hours manually overriding the system's recommendations. We need this fixed or we're evaluating alternatives."
>
> -- VP Operations, Global Shipping Corp

---

### Acceptance Criteria

- [ ] Channel health score properly weights reliability at 70%, latency at 30%
- [ ] Hazmat corridor surcharge (15%) applied correctly
- [ ] Multi-leg plan includes leg_count field
- [ ] Weather factor multiplies (not adds to) base transit time
- [ ] Route risk returns average, not sum
- [ ] Node selection picks highest score, not lowest
- [ ] All related tests passing
