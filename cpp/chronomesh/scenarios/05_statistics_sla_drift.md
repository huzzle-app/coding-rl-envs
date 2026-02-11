# OPS-ALERT + SLACK THREAD: SLA Metrics Drift and Policy Escalation Issues

## Alert Notification

```
ALERT: sla-metrics-drift
Severity: WARNING -> HIGH (escalated)
Time: 2024-11-13 16:45 UTC
Source: chronomesh-analytics

Anomaly detected in SLA percentile calculations:
- p95 response time showing 15% higher than actual
- Sample variance calculations diverging from expected
- Policy engine escalating prematurely

Dashboard: https://chronomesh-internal.port/grafana/d/sla-tracking
```

---

## Slack Thread: #chronomesh-ops

**Sarah Chen (SRE)** - 16:47
> Just got paged for SLA drift. Anyone else seeing weird percentile numbers? Our p95 latency shows 847ms but spot-checking the raw data it should be closer to 720ms.

**Marcus Webb (Data Eng)** - 16:49
> Looking at it now. The percentile calculation seems off. Let me pull some test data...

**Marcus Webb (Data Eng)** - 16:53
> Found something. When I calculate p90 for a 10-element array, the rank calculation is wrong:
> ```
> values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
> p90 calculation:
>   rank = (90 * 10 + ???) / 100
> ```
> The formula is adding something that pushes the rank too high. We're returning the 10th element (100) instead of the 9th element (90).

**Sarah Chen (SRE)** - 16:55
> That would explain the inflated latency numbers. What about the variance issue?

**Marcus Webb (Data Eng)** - 17:02
> Variance is also wrong. We're computing population variance instead of sample variance.
> For sample variance you divide by (n-1), not n.
>
> Example:
> ```
> values = [2, 4, 4, 4, 5, 5, 7, 9]
> mean = 5
> sum_sq = 32
>
> Population variance: 32/8 = 4.0
> Sample variance: 32/7 = 4.57
>
> We're returning 4.0 when statistical tools expect 4.57
> ```

**Jennifer Torres (Platform Lead)** - 17:05
> This is concerning. Our capacity planning models depend on accurate variance. No wonder the predictions have been off.

---

**Alex Kumar (Ops)** - 17:12
> Separate issue but related - the policy engine is escalating way too aggressively. We went from "normal" to "watch" after a single failure burst.

**Sarah Chen (SRE)** - 17:14
> What's the threshold supposed to be?

**Alex Kumar (Ops)** - 17:16
> According to the spec, escalation should happen at 2+ failures in a burst. But we're escalating at 1 failure.
>
> ```
> policy.escalate(1, "test failure")
> // Should stay at "normal" (threshold is 2+)
> // Actually escalates to "watch"
> ```

**Jennifer Torres (Platform Lead)** - 17:18
> And de-escalation? We've been stuck in "watch" mode even after 6 consecutive successes.

**Alex Kumar (Ops)** - 17:21
> Just tested. De-escalation threshold for "watch" is 4 successes (2 * 2).
> But `should_deescalate("watch", 4)` returns false.
> It only returns true at 5+ successes. Off by one somewhere.

---

**Marcus Webb (Data Eng)** - 17:35
> Let me also check the queue shedding logic since that feeds into the policy engine...

**Marcus Webb (Data Eng)** - 17:42
> Found another issue. Emergency shedding has a boundary problem:
> ```
> hard_limit = 100
> emergency_ratio = 0.8
> emergency_threshold = 80
>
> should_shed(80, 100, true)
> // Condition: 80 > 80 is FALSE
> // Should return TRUE (at threshold)
> // Actually returns FALSE
> ```
> We're using `>` instead of `>=` for the emergency check.

**Sarah Chen (SRE)** - 17:45
> And the wait time estimation?

**Marcus Webb (Data Eng)** - 17:48
> Oh man. `estimate_wait_time(depth=10, rate=2.0)`:
> - Expected: 10 / 2.0 = 5 seconds
> - Actual: 10 * 2.0 = 20 seconds
>
> We're multiplying instead of dividing. No wonder the queue depth alerts are firing when the queue is nearly empty.

---

**Jennifer Torres (Platform Lead)** - 18:00
> Summary of issues found:
> 1. Percentile rank calculation off-by-one (using +100 instead of +99)
> 2. Variance using population formula instead of sample (dividing by n instead of n-1)
> 3. Policy escalation threshold off-by-one (triggers at 1 instead of 2+)
> 4. Policy de-escalation threshold off-by-one (needs n+1 instead of n successes)
> 5. Emergency shedding boundary using `>` instead of `>=`
> 6. Wait time estimation multiplying instead of dividing
>
> All of these need fixes. Assigning to platform team for tomorrow morning.

---

## Files to Investigate

- `src/statistics.cpp`: `percentile()`, `variance()`
- `src/policy.cpp`: `next_policy()`, `should_deescalate()`
- `src/queue.cpp`: `should_shed()`, `estimate_wait_time()`

## Test Reproduction

Run the test suite with verbose output to see specific assertion failures:

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

Focus on tests related to:
- Percentile calculations
- Variance/standard deviation
- Policy state transitions
- Queue shedding decisions
- Wait time estimates
