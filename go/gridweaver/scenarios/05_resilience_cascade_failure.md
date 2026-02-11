# Post-Mortem Draft: Cascading Failure in Grid Control System

**Incident Date**: 2024-03-25
**Duration**: 4 hours 23 minutes
**Severity**: SEV-1 (Critical)
**Status**: Draft - Pending Review

---

## Incident Summary

A routine maintenance window triggered a cascading failure in GridWeaver's resilience subsystem. What should have been graceful degradation instead resulted in:

1. Circuit breakers opening prematurely
2. Retry storms overwhelming backend services
3. Load shedding removing high-priority traffic first
4. Recovery taking 10x longer than expected

The root causes span multiple bugs in the resilience and concurrency packages that combined to create a perfect storm.

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 14:00 | Scheduled maintenance begins on PostgreSQL cluster |
| 14:02 | First connection failures detected, retry logic engaged |
| 14:05 | Circuit breakers begin opening unexpectedly |
| 14:08 | Load shedding activates - critical traffic dropped first |
| 14:12 | Worker pool deadlocks under load |
| 14:15 | Retry backoff returning negative values, causing immediate retries |
| 14:20 | Full cascade - all services degraded |
| 14:45 | Manual intervention to disable faulty resilience logic |
| 16:30 | Maintenance complete, systems recovering |
| 18:23 | Full service restored |

## Detailed Findings

### Finding 1: Circuit Breaker Opening Too Early

The circuit breaker was configured with a threshold of 5 failures before opening, but it was opening after only 3 failures.

**Observed Behavior:**
```
[14:05:12] failures=3 threshold=5 state=OPEN (should be HALF-OPEN or CLOSED)
[14:05:13] failures=4 threshold=5 state=OPEN
```

Investigation suggests the threshold comparison is offset by 2 (using `threshold-2` instead of `threshold`).

### Finding 2: Retry Budget Not Enforced

The retry budget of 100 retries per minute was being ignored. Services continued retrying indefinitely.

```
Retry Budget: 100/minute
Actual Retries (14:10-14:11): 4,847
RetryBudget() always returning: true (should return false when budget exhausted)
```

### Finding 3: Negative Backoff Values

Retry backoff calculations were returning negative milliseconds, causing immediate retries instead of exponential backoff:

```
Attempt 1: backoff = -100ms (executed immediately)
Attempt 2: backoff = -200ms (executed immediately)
Attempt 3: backoff = -400ms (executed immediately)
```

This created a retry storm that amplified the original failure.

### Finding 4: Bulkhead Permitting When Full

The bulkhead pattern was supposed to limit concurrent requests to 50, but it was allowing requests through when at capacity:

```
Active connections: 50
Max concurrent: 50
BulkheadPermit() returned: true (should be false - at capacity)
```

The comparison appears inverted (`active > max` instead of `active < max`).

### Finding 5: Timeout Calculation Inverted

Timeout checks were computing elapsed time incorrectly:

```
Start time: 1000ms
Current time: 1500ms
Expected elapsed: 500ms
Actual computed: -500ms (startMs - nowMs instead of nowMs - startMs)
```

Negative elapsed time meant timeouts never triggered.

### Finding 6: Load Shedding Removing Critical Traffic First

When load shedding activated, it was removing high-priority requests first instead of low-priority:

```
Shed order (observed): ["critical-dispatch", "high-forecast", "medium-settlement", "low-audit"]
Expected order: ["low-audit", "medium-settlement", "high-forecast", "critical-dispatch"]
```

Priority sorting was reversed.

### Finding 7: Health Score Calculation Wrong

Service health scores were showing negative values during recovery:

```
Successes: 80, Failures: 20
Expected health: 0.80 (80%)
Actual health: 0.60 (formula using successes-failures instead of successes/total)
```

With more failures, health would go negative, preventing recovery detection.

### Finding 8: Graceful Degradation Mislabeled

At 95%+ load, the system should report "critical" status, but it was reporting "normal":

```
Load: 98%
Expected status: "critical"
Actual status: "normal"
```

This masked the severity from monitoring systems.

### Finding 9: Recovery Delay Capped Too Low

Recovery attempts were being delayed by at most 1 second instead of the expected 30 seconds:

```
Attempt 5 delay: 1000ms (should be ~16000ms with exponential backoff)
Attempt 6 delay: 1000ms (should be ~30000ms capped)
```

This caused services to retry recovery too aggressively, overwhelming recovering backends.

### Finding 10: Dispatch Replay Skipping All Events

The event replay mechanism was skipping all valid events due to inverted version comparison:

```
Current version: 100
Events: [version 50, version 75, version 100]
Events applied: 0 (should apply events with version <= 100)
```

The condition `e.Version > s.Version` was skipping events that should be included.

### Finding 11: Worker Pool Deadlock

The concurrency package's worker pool uses an unbuffered task channel, causing deadlock when submitting more tasks than workers:

```
Workers: 4
Tasks submitted: 10
Status: DEADLOCKED (4 tasks processing, 6 blocked on channel send)
```

### Finding 12: Fan-Out Not Waiting for Completion

FanOut returns before goroutines complete, returning uninitialized results:

```
FanOut(["a", "b", "c"], processFunc)
Returned immediately with: ["", "", ""] (empty - goroutines still running)
```

### Finding 13: Pipeline Channel Never Closed

Pipeline consumers hung waiting for more data because the output channel was never closed:

```
for result := range Pipeline(input, transform) {
    // Never terminates - channel not closed
}
```

### Finding 14: Merge Channels Race Condition

MergeChannels has a race where one goroutine closes the output channel while another is still writing:

```
panic: send on closed channel
```

### Finding 15: Batch Collect Data Race

BatchCollect appends to a shared slice from multiple goroutines without synchronization:

```
WARNING: DATA RACE
Write at 0x... by goroutine 15:
  runtime.growslice()
Previous write at 0x... by goroutine 16:
  runtime.growslice()
```

### Finding 16: Semaphore Logic Inverted

SemaphoreAcquire returns true when the semaphore is full instead of when it's available:

```
Current: 5, Max: 5
Expected: false (full, cannot acquire)
Actual: true (wrongly permits acquisition)
```

## Root Cause Analysis

The cascading failure resulted from multiple compounding bugs:

1. **Trigger**: Database maintenance caused transient connection failures
2. **Amplification**: Negative backoff + no retry budget = retry storm
3. **Wrong Response**: Circuit breakers opened early, load shedding shed critical traffic
4. **Blocked Recovery**: Timeout never triggered, health scores wrong, recovery capped too low
5. **Concurrency Failures**: Worker pool deadlocked, races in parallel processing

## Affected Packages

- `internal/resilience/simulator.go` - Circuit breaker, retry, load shedding, recovery
- `internal/concurrency/pool.go` - Worker pool, fan-out, pipeline, channel merge
- `internal/workflow/orchestrator.go` - Counter increment, parallel collection races

## Recommended Remediations

1. Fix all comparison operators in resilience threshold checks
2. Correct backoff calculation (remove negation)
3. Implement retry budget enforcement
4. Fix load shedding priority order
5. Correct timeout elapsed time calculation
6. Buffer worker pool task channel
7. Add WaitGroup to FanOut
8. Close pipeline output channels
9. Use mutex for MergeChannels coordination
10. Protect BatchCollect with synchronization

## Lessons Learned

- Multiple small bugs in resilience code can combine catastrophically
- Resilience mechanisms themselves need thorough testing
- Chaos engineering would have revealed these issues earlier
- Sort order bugs (ascending vs descending) are common and dangerous

---

**Author**: Incident Commander
**Reviewers**: Platform Engineering, SRE, Architecture
**Status**: Pending final review
