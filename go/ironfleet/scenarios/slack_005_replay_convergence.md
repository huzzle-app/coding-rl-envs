# Slack Discussion: #ironfleet-oncall

**Channel:** #ironfleet-oncall
**Date:** 2024-03-20

---

**@chen.wei** [09:12 AM]
Hey team, seeing something weird with the event replay system. Convoys are losing telemetry events during failover recovery.

---

**@ops-bot** [09:12 AM]
:rotating_light: Alert: `ReplayEventLoss` firing for `ironfleet-resilience` in `us-east-1`

---

**@sarah.k** [09:14 AM]
@chen.wei What's the symptom exactly?

---

**@chen.wei** [09:15 AM]
When we replay events after a node failover, we're only getting back 1 event instead of the full deduplicated set. Running a test locally:

```
replayed := resilience.Replay([]resilience.Event{
    {ID: "convoy-1", Sequence: 1},
    {ID: "convoy-1", Sequence: 2},
    {ID: "convoy-2", Sequence: 1},
})
// Expected: 2 events (convoy-1 seq 2, convoy-2 seq 1)
// Actual: 1 event only
```

It's like the replay is only keeping the last event processed, not the full deduplicated result.

---

**@jordan.m** [09:17 AM]
Oh that's bad. We rely on replay convergence for the whole contested-network recovery flow.

---

**@chen.wei** [09:18 AM]
Yeah. Test suite is also unhappy:
```
=== FAIL: TestReplayLatestSequenceWins
    replay_test.go:11: unexpected replay output: [{ID:x Sequence:2}]

=== FAIL: TestHyperMatrix/case_00001
    hyper_matrix_test.go:91: replay too small: [{ID:z-1 Sequence:1}]
```

It should return all unique event IDs with their highest sequence numbers.

---

**@sarah.k** [09:20 AM]
@chen.wei Can you pull the trace from the last failover?

---

**@chen.wei** [09:22 AM]
Here's what I'm seeing in the resilience service logs:
```
2024-03-20T08:45:12Z DEBUG Replay invoked events_count=847
2024-03-20T08:45:12Z DEBUG processing event_id="convoy-alpha" seq=1
2024-03-20T08:45:12Z DEBUG processing event_id="convoy-alpha" seq=2
2024-03-20T08:45:12Z DEBUG processing event_id="convoy-bravo" seq=1
... (845 more events)
2024-03-20T08:45:13Z INFO  Replay complete result_count=1
```

847 events in, 1 event out. That's definitely wrong.

---

**@jordan.m** [09:24 AM]
I bet it's overwriting the result instead of accumulating. Classic accumulator bug.

---

**@priya.r** [09:25 AM]
Also noticed the chaos tests are failing:
```
=== FAIL: TestReplayOrderedAndShuffledConverge
    replay_test.go:19: expected replay equivalence
```

The replay should be deterministic regardless of input order. If we shuffle the input events, we should get the same output.

---

**@chen.wei** [09:27 AM]
Good catch. That's the whole point of idempotent replay - network partitions mean events arrive out of order, but convergence should produce the same result.

---

**@sarah.k** [09:28 AM]
What's the operational impact right now?

---

**@chen.wei** [09:30 AM]
Pretty significant:
- Convoy telemetry incomplete after failovers
- Position tracking gaps of 15-30 seconds
- Mission log has holes where events were "lost" during replay

Metrics:
```
ironfleet_replay_event_loss_ratio 0.94
ironfleet_replay_convergence_failures_total 234
ironfleet_telemetry_gaps_total{type="replay"} 1847
```

We're losing 94% of events during replay. Not great.

---

**@jordan.m** [09:32 AM]
Related question - is the checkpoint logic also affected? We rely on replay for checkpoint recovery too.

---

**@chen.wei** [09:34 AM]
Haven't confirmed but wouldn't be surprised. The `MarkCheckpoint` and `DedupKey` functions all feed into the same replay flow.

Also noticed this comment in the code:
```go
// BUG: no stability check - relies on Replay which itself has the lowest-sequence bug
```

So there's definitely some known issues in that file.

---

**@priya.r** [09:36 AM]
Should we page the platform team or can oncall handle?

---

**@sarah.k** [09:37 AM]
Let's try to fix in the next hour. @chen.wei can you take point? Focus on `internal/resilience/replay.go` - the Replay function logic specifically.

---

**@chen.wei** [09:38 AM]
On it. Will also check the circuit breaker and dedup logic while I'm in there - saw some related BUG comments.

---

**@ops-bot** [09:40 AM]
:chart_with_upwards_trend: Metric spike: `ironfleet_mission_state_inconsistency_total` increased 340% in last 30m

---

**@jordan.m** [09:41 AM]
That's downstream of the replay issue. @chen.wei LMK if you need a second pair of eyes.

---

**@chen.wei** [09:42 AM]
Will do. Key tests to verify fix:
- `TestReplayLatestSequenceWins`
- `TestReplayOrderedAndShuffledConverge`
- Stress suite: `TestHyperMatrix` (7000 cases)

---

**@sarah.k** [09:43 AM]
:thumbsup: Keep us posted in thread.
