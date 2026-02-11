# Incident Report: Cascading Failures and Circuit Breaker Malfunction

## PagerDuty Incident #INC-2024-0892

**Severity**: Critical (P0)
**Triggered**: 2024-03-25 02:47 UTC
**Resolved**: 2024-03-25 06:15 UTC (manually)
**Team**: Platform Reliability Engineering
**Postmortem Due**: 2024-03-28

---

## Incident Summary

At 02:47 UTC, the variant annotation service experienced a brief network partition from its database cluster. Instead of the circuit breaker opening and failing fast, the system entered a retry storm that cascaded into a full platform outage. The circuit breaker was supposed to protect downstream services but instead made things worse.

## Timeline

**02:45 UTC** - Network blip causes 3 consecutive failures to variant annotation DB

**02:47 UTC** - Circuit breaker should have opened (threshold: 5 failures) but remained CLOSED

**02:48 UTC** - More requests pile up, each failing and retrying

**02:50 UTC** - Load shedding engaged but triggered too early (at exactly 100 in-flight, not > 100)

**02:52 UTC** - Exponential backoff not increasing fast enough, retry storms continue

**02:55 UTC** - Downstream cohort aggregator overwhelmed

**03:00 UTC** - Full pipeline gridlock - all samples stuck

**03:15 UTC** - On-call manually disabled retries

**06:15 UTC** - Full recovery after manual intervention

## Technical Analysis

### Problem 1: Circuit Breaker Opens Too Early

The circuit breaker is configured with `threshold: 3` but should be `threshold: 5`:

```
Observed behavior:
  Failure 1: state=Closed, failure_count=1
  Failure 2: state=Closed, failure_count=2
  Failure 3: state=Open, failure_count=3  <-- Opens at 3!

Expected behavior:
  Should only open after MORE than 5 failures
```

Additionally, the circuit breaker opens when `failure_count >= threshold` instead of `> threshold`:

```
Expected: Open after 6th failure (when count > 5)
Actual: Opens at 3rd failure (when count >= 3)
```

### Problem 2: Half-Open State Doesn't Allow Probe Requests

When we try to probe if the service has recovered:

```
cb.try_half_open()
Expected: state=HalfOpen, returns true (allow probe request)
Actual: state=HalfOpen, returns false (blocks probe request!)
```

The circuit breaker gets stuck in Open state because the probe to test recovery is never allowed through.

### Problem 3: Load Shedding Triggers at Wrong Threshold

```
in_flight_requests: 100
limit: 100

should_shed_load(100, 100)
Expected: false (100 is exactly at limit, not over)
Actual: true (uses >= instead of >)
```

This caused premature load shedding, dropping requests that should have been processed.

### Problem 4: Exponential Backoff Too Slow

```
Attempt | Expected (base 100ms, mult 2.0) | Actual (mult 1.5)
--------|----------------------------------|------------------
1       | 200ms                            | 150ms
2       | 400ms                            | 225ms
3       | 800ms                            | 337ms
4       | 1600ms                           | 506ms
5       | 3200ms                           | 759ms
```

The backoff multiplier of 1.5 instead of 2.0 means retries come back too fast.

### Problem 5: Backoff Cap Calculation Wrong

```
max_backoff: 5000ms
calculated_backoff: 6000ms

capped_backoff(...)
Expected: 5000ms (just return max)
Actual: 4900ms (subtracts 100 for some reason??)
```

### Problem 6: Remaining Retries Off By One

```
max_retries: 5
attempts: 2

remaining_retries(5, 2)
Expected: 3 (5 - 2 = 3)
Actual: 2 (5 - 2 - 1 = 2)
```

This causes pipelines to give up one retry early.

### Problem 7: Fail-Fast Check Uses Wrong Operator

```
attempts: 5
max_retries: 5

should_fail_fast(5, 5)
Expected: true (5 >= 5, should stop)
Actual: false (uses > instead of >=)
```

Combined with Problem 6, this creates zombie retries that never stop.

### Problem 8: Replay Window Accepting Wrong Events

The event replay for recovery is accepting stale events:

```
event_timestamp: 1000
watermark_timestamp: 1050
skew_tolerance: 10

replay_window_accept(1000, 1050, 10)
Expected: false (event is 50ms old, tolerance is only 10ms)
Actual: true (formula is wrong: event + tolerance >= watermark)
Correct: event >= watermark - tolerance (1000 >= 1040 = false)
```

### Problem 9: Burst Policy Returns Wrong Max In-Flight

```
failure_burst_count: 7

burst_policy_max_inflight(7)
Expected: 4 (severe burst, reduce to 4)
Actual: 8 (wrong threshold mapping)
```

During high failure bursts, we're allowing TOO MANY in-flight requests instead of reducing them.

---

## Metrics During Incident

### Circuit Breaker State (02:45-03:00 UTC)
```
Time    | Failures | Expected State | Actual State
--------|----------|----------------|-------------
02:45:00| 1        | Closed         | Closed
02:45:30| 2        | Closed         | Closed
02:46:00| 3        | Closed         | Open (!)
02:46:30| 4        | Open           | Open
02:47:00| probe    | HalfOpen       | Stuck Open
```

### Retry Storm Metrics
```
Minute  | Retry Requests | Normal Requests | Ratio
--------|---------------|-----------------|-------
02:45   | 12            | 847             | 1.4%
02:50   | 3,421         | 234             | 93.6%
02:55   | 12,847        | 12              | 99.9%
03:00   | 28,444        | 0               | 100%
```

### Backoff Distribution
```
Actual backoff times (should be doubling):
  Attempt 1: 150ms (expected: 200ms)
  Attempt 2: 225ms (expected: 400ms)
  Attempt 3: 337ms (expected: 800ms)
```

---

## Root Cause

Multiple bugs in the resilience module caused a chain reaction:

1. Circuit breaker threshold too low (3 vs 5)
2. Opens at >= instead of > threshold
3. Half-open probe blocked, preventing recovery detection
4. Backoff too slow (1.5x vs 2.0x), retries come back too fast
5. Load shedding too aggressive (>= vs >)
6. Remaining retry count off by one
7. Fail-fast check never triggers (> vs >=)

Each bug individually might have been tolerable, but together they created a cascading failure.

---

## Customer Impact

- 2,847 samples delayed by 3+ hours
- 12 clinical reports missed overnight delivery deadline
- 3 research partners received late cohort data
- Estimated revenue impact: $45,000 in SLA credits

---

## Remediation Tasks

1. Fix circuit breaker threshold: 3 -> 5
2. Fix threshold comparison: >= to >
3. Fix half-open to return true for probe
4. Fix backoff multiplier: 1.5 -> 2.0
5. Fix backoff cap to just return max
6. Fix remaining retries calculation
7. Fix fail-fast comparison: > to >=
8. Fix load shedding comparison: >= to >
9. Fix burst policy thresholds
10. Add integration tests for failure scenarios

---

**Status**: POSTMORTEM PENDING
**Assigned**: @reliability-team
**Follow-up**: Chaos engineering tests scheduled for 2024-04-01
