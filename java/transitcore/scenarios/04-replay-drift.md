# Slack Thread: State Reconstruction Errors After Failover

## #platform-engineering - January 21, 2024

---

**@sre.marcus** (14:23):
> We just failed over from primary to secondary datacenter and our resilience layer is showing weird state. The replay mechanism reconstructed the wrong counts.

**@sre.marcus** (14:24):
> Dashboard screenshot:
```
Pre-failover state (Primary DC):
  - Inflight: 245
  - Backlog: 1,892
  - Version: 10500

Post-replay state (Secondary DC):
  - Inflight: 242
  - Backlog: 1,888
  - Version: 10500
  - Applied events: 3 (should be 4)
```

**@sre.marcus** (14:25):
> We're missing one event from the replay. And the counts are off by 3-4 units on each counter.

---

**@dev.priya** (14:32):
> Let me look at the event log. What events were pending during the failover?

**@sre.marcus** (14:35):
> Here's the event stream we tried to replay:
```
Version  IdempotencyKey  InflightDelta  BacklogDelta
10500    evt-500         +3             -5
10501    evt-501         +1             -2
10502    evt-502         -1             +1
10503    evt-503         +2             -3
```

**@sre.marcus** (14:36):
> Base state was inflight=245, backlog=1892, version=10500
> After replay should be: inflight=250, backlog=1883, version=10503, applied=4

---

**@dev.priya** (14:40):
> I think I see the issue. Look at the first event - version 10500.

**@dev.priya** (14:41):
> Our base version is 10500, and the first event is ALSO version 10500. The replay logic is supposed to skip events AT the current version (we already have those), and only apply events AFTER the current version.

**@dev.priya** (14:42):
> But I think there's an off-by-one. Let me check the code...

**@dev.priya** (14:48):
> Found it. The version check is using `<=` instead of `<`. We're skipping events at the CURRENT version when we should only skip events BELOW the current version.

```
if (event.version() <= version) {  // This is wrong
    continue;
}
```

**@dev.priya** (14:49):
> Should be `< version`, not `<= version`. Event at version 10500 should be applied since we have state AT 10500, not AFTER 10500.

---

**@sre.marcus** (14:52):
> That explains the missing event. But we're still seeing other replay issues too.

**@sre.marcus** (14:53):
> This morning we had a different problem. After a pod restart, the circuit breaker was staying open way too long.
```
Recent failures: 5
Expected: Circuit CLOSED (opens at 6+)
Actual: Circuit OPEN
```

**@dev.priya** (14:58):
> Same pattern. The circuit breaker check is using `> 5` instead of `>= 6`. It's opening at exactly 5 failures when it shouldn't.

---

**@dev.alex** (15:05):
> While you're in the resilience code, can you also check the retry backoff? Operations reported that retry delays are double what they expect.

**@dev.alex** (15:06):
> For a first retry (attempt=1, baseMs=100):
```
Expected: 100ms (100 * 2^0)
Actual: 200ms (100 * 2^1)
```

**@dev.priya** (15:12):
> Yeah, the power calculation is using `attempt` directly instead of `attempt - 1`. First attempt (1) should have power 0, not power 1.

---

**@sre.marcus** (15:18):
> OK so we have at least three issues in the resilience layer:
> 1. Replay version check skipping current-version events
> 2. Circuit breaker opening at 5 failures instead of 6
> 3. Retry backoff power is off by one

**@dev.priya** (15:20):
> I'm also seeing the same backoff issue in the retry budget code. Same pattern - using attempt instead of attempt-1.

**@dev.alex** (15:25):
> And there's another retry bug while you're in there. The `shouldRetry` function is allowing one extra retry:
```
maxAttempts=3, attempt=3, circuitOpen=false
Expected: false (attempt 3 of 3, no more retries)
Actual: true (still trying)
```

**@dev.priya** (15:28):
> Using `<=` instead of `<` for the attempt check. It's retry when `attempt <= max` but should be `attempt < max`.

---

**@sre.marcus** (15:35):
> This explains a lot of the weird behavior we've been seeing. The system is more aggressive on retries than expected AND opens circuit breakers too early AND misses events during replay.

**@dev.priya** (15:38):
> I'll put together fixes. All of these are comparison operator issues - off-by-one errors in the thresholds.

**@sre.marcus** (15:40):
> Please also check if the penalty score calculation is right. Finance was asking why our penalty numbers look higher than expected.

**@dev.priya** (15:45):
> Let me check... yep. Penalty score uses `retries * 3` but should be `retries * 2`. That's a 50% inflation in the retry penalty component.

---

## Summary

| Component | Issue | Impact |
|-----------|-------|--------|
| Event replay | Skipping events at current version | State drift after failover |
| Circuit breaker | Opens at 5 failures, should be 6 | Premature service degradation |
| Retry backoff (x2) | Power off by one | Double the expected delay |
| Retry budget | Extra retry attempt | Resource exhaustion |
| Penalty score | Wrong multiplier | Inflated scoring |

## Files to Investigate

- Resilience replay module
- Retry budget service
- Queue governor (for related throttle issues)

---

**Thread Status**: Active investigation
**Fix ETA**: EOD January 21
