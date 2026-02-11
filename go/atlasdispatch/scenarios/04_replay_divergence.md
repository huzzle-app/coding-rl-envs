# Slack Discussion: Event Replay Producing Inconsistent State

**Channel:** #platform-reliability
**Date:** 2024-11-14

---

**@sarah.martinez** (09:14 AM)
Hey team, we're seeing something weird with event replay in the disaster recovery tests. When we replay the same event stream on two different nodes, they end up with different final states. Isn't replay supposed to be deterministic?

**@david.chen** (09:17 AM)
That's concerning. What's the scenario?

**@sarah.martinez** (09:19 AM)
We have an event stream with duplicate events (same ID, different sequence numbers). The replay function should deduplicate and keep the latest version of each event. But when I check the output, it's keeping the OLDEST version instead.

Example:
```
Input events:
  {ID: "ship-001", Sequence: 100}
  {ID: "ship-001", Sequence: 150}  <- This should be kept (latest)
  {ID: "ship-001", Sequence: 120}

Expected output: {ID: "ship-001", Sequence: 150}
Actual output:   {ID: "ship-001", Sequence: 100}
```

**@david.chen** (09:22 AM)
Oh that's bad. The comparison operator must be flipped. Let me look at the Replay function...

**@priya.patel** (09:25 AM)
While you're looking, we also have issues with the checkpoint manager. The `ShouldCheckpoint` function seems off by one. We configured checkpoints every 1000 events but they're triggering at 1001 instead.

**@sarah.martinez** (09:28 AM)
Yes! That matches what we're seeing. Here's our test:
```
lastSequence = 0
currentSeq = 1000
ShouldCheckpoint(1000) -> returns false (should be true)
ShouldCheckpoint(1001) -> returns true
```

**@david.chen** (09:31 AM)
Found something else while looking. The `Deduplicate` function has a subtle bug with sequence numbers. It's using `string(rune(e.Sequence))` to build the dedup key. That works fine for small sequences, but rune conversion gets weird above 127.

**@priya.patel** (09:34 AM)
Can you elaborate? We do have sequences in the millions.

**@david.chen** (09:36 AM)
```go
// For sequence 128:
string(rune(128)) // produces Unicode character, not "128"

// So {ID: "A", Sequence: 128} and {ID: "A", Sequence: 256}
// could potentially have key collisions
```

**@sarah.martinez** (09:40 AM)
That explains the state divergence we saw in the long-running replay tests! Events with high sequence numbers are incorrectly deduplicated.

**@marcus.wong** (09:43 AM)
Hey all, jumping in from SRE. We're also seeing circuit breaker issues. The half-open state isn't rate limiting at all - it's letting through 100% of traffic. We expected it to allow limited probe requests.

**@david.chen** (09:45 AM)
@marcus.wong that's in the same resilience package. The `IsAllowed()` function just returns true for half-open state. No rate limiting logic.

**@marcus.wong** (09:48 AM)
Also, closing the circuit takes 4 consecutive successes instead of 3. We configured 3 but it's requiring one extra.

```
successThreshold = 3 (configured)
successes recorded: 1, 2, 3 -> still half-open
success #4 -> finally closes
```

**@priya.patel** (09:52 AM)
Sounds like another off-by-one. Uses `> 3` instead of `>= 3`?

**@david.chen** (09:54 AM)
Exactly. I'll file bugs for all of these:

1. Replay keeps oldest instead of latest (comparison inverted)
2. Checkpoint trigger off-by-one (`>` vs `>=`)
3. Deduplicate key collision for sequences > 127
4. Half-open state allows all traffic (no rate limiting)
5. Circuit close requires n+1 successes

**@sarah.martinez** (09:57 AM)
Thanks David. These need to be fixed before the DR drill next week. The replay divergence alone could cause us to restore to an inconsistent state.

**@marcus.wong** (10:01 AM)
Agreed. Without proper circuit breaker behavior, a cascading failure could take down the whole fleet management system.

---

**Thread: Investigating P99 Statistics Anomaly**

**@analytics-bot** (10:15 AM)
Alert: P99 latency metrics showing 15% lower than expected. Percentile calculation may be incorrect.

**@david.chen** (10:18 AM)
Looking at the percentile functions. The rank formula has `+ 50` but for proper percentile calculation it should be `+ 99`. This would consistently underreport high percentiles.

**@priya.patel** (10:21 AM)
So our "P99" is actually more like P50? No wonder our SLO reports look good but customers are complaining.

**@david.chen** (10:24 AM)
Essentially, yes. Both `Percentile()` and `percentileFloat()` have the same bug. We're measuring the wrong thing across the board.

---

**Summary from @david.chen** (11:00 AM)
Created tracking issues for resilience and statistics bugs:
- ATLAS-4521: Replay comparison inverted
- ATLAS-4522: Checkpoint off-by-one
- ATLAS-4523: Deduplicate key collision
- ATLAS-4524: Half-open allows all traffic
- ATLAS-4525: Circuit close threshold off-by-one
- ATLAS-4526: Percentile formula incorrect
