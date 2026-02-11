# Scenario 05: Analytics Dashboard Drift

## Type: Dashboard Alert / Analytics Review

## Source: Weekly Metrics Review Meeting

---

### Meeting Notes: Q4 Analytics Discrepancy Review

**Date**: 2024-12-13
**Attendees**: Analytics Team, Platform Engineering, Operations

---

#### Agenda Item 1: P95 Latency Reporting Anomaly

**Analytics Lead**:

Our P95 latency numbers have been consistently higher than what customers report experiencing. We sampled 1000 requests and our internal tooling shows P95 = 245ms, but the platform dashboard shows P95 = 312ms.

**Platform Engineer**:

The percentile calculation might have an off-by-one issue. Let me walk through the math:

For 1000 samples at P95:
- Correct rank: `(95 * 1000 + 99) / 100 - 1 = 949` (950th element, 0-indexed as 949)
- Our formula: `(95 * 1000 + 100) / 100 - 1 = 950`

We're reading one position too high in the sorted array, which at P95 means we're reporting a slightly higher latency.

**Analytics Lead**:

That explains the 27% overreporting we're seeing. At tail percentiles, even one index off makes a noticeable difference.

---

#### Agenda Item 2: Variance Calculation for Capacity Planning

**Operations Manager**:

Our capacity models are predicting 15% more variance in processing times than we actually observe. This is causing us to over-provision resources.

**Platform Engineer**:

I checked the `variance` function. We're using Bessel's correction (dividing by n-1) which is for sample variance, but we're treating it as population variance in our capacity formulas.

**Analytics Lead**:

If we have 100 data points:
- Population variance divides sum of squares by 100
- Sample variance divides by 99

That's a ~1% inflation at n=100, but for smaller datasets (n=10), it's ~11% inflation.

**Operations Manager**:

We often compute variance over 10-minute windows with ~20 samples. That's 5% inflation built into every calculation.

---

#### Agenda Item 3: Route Cost Underestimation

**Finance Lead**:

Route cost estimates are consistently 10-15% below actual invoiced amounts. We're seeing this pattern across all shipping lanes.

**Operations Manager**:

Here's an example:
- Distance: 500 nautical miles
- Fuel rate: $2.50/nm
- Port fee: $1,250

Expected cost: `500 * 2.50 + 1250 = $2,500`
System shows: `500 * 2.50 - 1250 = $0` (clamped to 0)

**Platform Engineer**:

The formula is subtracting port fees instead of adding them. For short routes with high port fees, we're showing $0 cost which is why finance is seeing such a discrepancy.

---

#### Agenda Item 4: Channel Scoring for Route Selection

**Operations Manager**:

Our automated route selection is favoring unreliable channels. A channel with 99% reliability and priority 5 is scoring the same as one with 94% reliability and priority 10.

**Platform Engineer**:

The channel score formula is:
```
(reliability + priority) / latency
```

It should be:
```
(reliability * priority) / latency
```

With addition:
- Channel A: (0.99 + 5) / 10 = 0.599
- Channel B: (0.94 + 10) / 10 = 1.094

With multiplication:
- Channel A: (0.99 * 5) / 10 = 0.495
- Channel B: (0.94 * 10) / 10 = 0.94

The bug makes low-reliability-high-priority channels look much better than they should.

---

#### Agenda Item 5: Heavy Vessel Classification

**Port Authority Liaison**:

We're getting compliance warnings for vessels at exactly 50,000 tons cargo weight. They should be classified as "standard" but the system marks them as "heavy", triggering unnecessary inspections.

**Platform Engineer**:

The threshold check uses `>= 50000` instead of `> 50000`. Vessels at exactly 50,000 tons are being incorrectly classified.

---

### Action Items

1. Fix percentile rank calculation (off-by-one in formula)
2. Decide on sample vs population variance and update accordingly
3. Correct route cost formula (subtract -> add for port fees)
4. Fix channel score formula (add -> multiply for reliability)
5. Adjust heavy vessel threshold (>= to >)

### Affected Modules

- `src/statistics.rs` - percentile, variance
- `src/routing.rs` - channel_score, estimate_route_cost
- `src/models.rs` - is_heavy

---

**Meeting Adjourned**: 11:45 AM
**Next Review**: 2024-12-20
