# Slack Thread: #incident-response

---

**@sarah.kim** (Platform Engineering) - 2024-11-14 09:17 AM

:rotating_light: We're seeing capacity overload in the US-WEST dispatch cluster. Load shedding should have kicked in but it's not triggering. Current in-flight count is exactly at the hard limit (500) but no shed happening.

---

**@david.okonkwo** (SRE) - 2024-11-14 09:19 AM

Can confirm. Looking at metrics:
```
in_flight_requests: 500
hard_limit: 500
shed_triggered: false
```

The `shedRequired` function should return `true` when we hit the limit, but it's only triggering when we exceed it. That one-off difference is enough that we're sitting exactly at saturation.

---

**@sarah.kim** - 2024-11-14 09:21 AM

Same pattern yesterday during the APAC peak. We hit exactly 500 and sat there until organic traffic decay. No protective shedding.

Also noticed something weird with the `rebalance` function - it seems to be calculating available capacity wrong. We have a 50-unit reserve floor but it's being *added* to available instead of subtracted.

So if we have 200 available and 50 reserve, we should have 150 usable, but we're showing 250??

---

**@james.chen** (Capacity Planning) - 2024-11-14 09:24 AM

That explains the budget overruns. We've been allocating more capacity than we actually have available. Finance flagged this last week - our utilization reports don't match actual costs.

---

**@david.okonkwo** - 2024-11-14 09:27 AM

Found another issue in `dynamicBuffer`. The volatility coefficient seems off - we're getting way less buffer than expected for high-volatility periods. And the min/max clamping looks backwards?

Input: `volatilityScore=10, floor=0.1, cap=0.5`
Expected: something between 0.1 and 0.5
Actual: getting values outside that range

---

**@sarah.kim** - 2024-11-14 09:30 AM

Can someone run the capacity unit tests? I think they'll show these issues:

```
npm test -- tests/unit/capacity.test.js
```

---

**@david.okonkwo** - 2024-11-14 09:34 AM

Just ran them. Multiple failures:
- `shedRequired` boundary test failing
- `rebalance` reserve calculation off
- `dynamicBuffer` clamping inverted

The `>=` vs `>` on shed threshold is definitely wrong. And the reserve math is adding instead of subtracting.

---

**@james.chen** - 2024-11-14 09:38 AM

Priority: We have a major traffic surge expected in 4 hours (Black Friday pre-sale). If we can't shed properly, we'll cascade fail across regions.

---

**@sarah.kim** - 2024-11-14 09:40 AM

Acknowledged. Pulling in @oncall-platform. This needs eyes on `src/core/capacity.js` ASAP.

Key functions:
- `rebalance()` - reserve floor handling
- `shedRequired()` - boundary condition
- `dynamicBuffer()` - volatility coefficient and clamping

---

**Thread escalated to P1**
**Incident Commander:** @sarah.kim
