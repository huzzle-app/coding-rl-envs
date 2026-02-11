# Scenario 04: Telemetry and Resilience System Anomalies

## Slack Thread - #aero-platform-eng

---

**@jennifer.wu** (09:15 UTC)
Hey team, getting some weird reports from the telemetry dashboards. Anyone else seeing anomalies in the health scoring?

**@alex.petrov** (09:18 UTC)
Yeah, I've been debugging this all morning. The latency classification is completely wrong. A 52ms response is being classified as "fast" when it should be "medium". The threshold is at 51 instead of 50.

**@jennifer.wu** (09:21 UTC)
That might explain the alerting issues. Our SLO alerting is triggering when latency is BELOW the threshold instead of above it. We're getting paged for good performance and not getting paged for actual problems.

**@raj.mehta** (09:25 UTC)
Found something in the error rate calculation. It's doing `errors / (total - errors)` instead of `errors / total`. When you have 10 errors out of 100 requests, it returns 0.111 instead of 0.1.

**@alex.petrov** (09:29 UTC)
The mean response time function is broken too. It returns the SUM of all latencies instead of the mean. Dashboard shows "average latency: 4,500ms" when actual average is 45ms.

**@jennifer.wu** (09:33 UTC)
Availability calculation is wrong. Should be `uptime / total_time` but it's using `uptime - downtime`. That doesn't even produce a ratio.

**@raj.mehta** (09:38 UTC)
And the metric formatting uses commas as separators instead of colons. Our log parsers are breaking because they expect `metric:value` but they're getting `metric,value`.

**@alex.petrov** (09:42 UTC)
The threshold check is using strict less-than instead of less-than-or-equal. A value exactly at the threshold doesn't trigger.

**@jennifer.wu** (09:47 UTC)
Drift detection is returning signed values instead of absolute. Negative drift shows as negative even though we only care about magnitude.

**@raj.mehta** (09:52 UTC)
The "seconds since last event" function is returning the current epoch timestamp instead of the delta. No wonder our "time since last error" is showing as 1.7 billion seconds.

**@alex.petrov** (09:58 UTC)
And the unit labels are missing from formatted outputs. We're seeing raw numbers without "ms", "bytes", etc.

---

## Related Thread - #aero-resilience

---

**@sarah.kim** (10:15 UTC)
Resilience patterns are completely broken. Circuit breaker isn't tripping when it should.

**@michael.torres** (10:18 UTC)
I see that. The `should_trip` check uses `>` instead of `>=`. If threshold is 5 and we have exactly 5 failures, it doesn't trip.

**@sarah.kim** (10:22 UTC)
Exponential backoff is actually LINEAR. The retry_delay function does `base * attempt` instead of `base * 2^attempt`. Retries are way too aggressive.

**@michael.torres** (10:26 UTC)
The half-open state is allowing requests when it shouldn't. The condition checks `current > 0` instead of `current < max_probes`.

**@sarah.kim** (10:31 UTC)
Degradation level is inverted. Low error rates are labeled "critical" and high error rates are "minor".

**@michael.torres** (10:35 UTC)
Bulkhead remaining calculation returns the USED permits instead of remaining. If 3 out of 10 are used, it says 3 remaining instead of 7.

**@sarah.kim** (10:40 UTC)
The cascade failure check uses `all` instead of `any`. It only triggers if EVERY dependency is down, not when any single one fails.

**@michael.torres** (10:45 UTC)
Recovery rate formula is inverted - returns `total/recovered` instead of `recovered/total`.

**@sarah.kim** (10:50 UTC)
The failure window check is backwards. It returns true when the failure is OUTSIDE the window, not inside.

**@michael.torres** (10:55 UTC)
And the state duration returns milliseconds instead of seconds. Off by 1000x.

**@sarah.kim** (11:00 UTC)
Fallback value selection is swapped. When primary succeeds, it returns fallback. When primary fails, it returns primary.

**@michael.torres** (11:05 UTC)
Circuit reset condition checks for CLOSED state instead of OPEN. It tries to reset when already closed.

**@sarah.kim** (11:10 UTC)
Checkpoint interval calculation divides by 2 for some reason. Checkpoints happen twice as often as configured.

---

### Summary

Telemetry and resilience modules have widespread issues with:
- Inverted conditions
- Off-by-one errors
- Wrong mathematical operations
- Unit mismatches

### Files to Investigate

- `src/telemetry.rs` - Metrics, alerting, health scoring
- `src/resilience.rs` - Circuit breaker, retry, bulkhead patterns

### Reproduction

```bash
cargo test telemetry
cargo test metric
cargo test alert
cargo test resilience
cargo test circuit
cargo test retry
cargo test bulkhead
```
