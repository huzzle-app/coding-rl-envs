# Scenario 04: Policy Escalation Instability

## Type: Slack Discussion

## Channel: #vectorharbor-oncall

---

**@marina.chen** [09:15]
Anyone else seeing weird behavior with the policy engine this morning? We had a single transient failure and the system immediately escalated from `normal` to `watch` mode.

**@james.morrison** [09:17]
Wait, shouldn't it take at least 2 failures to escalate? That's what the runbook says.

**@marina.chen** [09:18]
That's what I thought! Looking at the logs:
```
[09:14:32] failure_burst=1, policy changed: normal -> watch
```
One failure should not trigger escalation.

**@sarah.patel** [09:22]
I'm seeing a related issue with de-escalation. We've been in `watch` mode with 5 consecutive successes, and the system isn't de-escalating back to `normal`.

**@james.morrison** [09:24]
The threshold for `watch` -> `normal` is 5 successes, right?

**@sarah.patel** [09:25]
Yes, but I have logs showing success_streak=5 and it's still in watch mode. It finally de-escalated when we hit success_streak=6.

**@marina.chen** [09:28]
So escalation is too sensitive (triggers on 1 instead of 2), and de-escalation is too strict (needs 6 instead of 5)?

**@devops-bot** [09:30]
:alert: Checkpoint alert: Resilience module missed scheduled checkpoint at sequence 1100. Last checkpoint was at sequence 1000. Interval configured as 100.

**@james.morrison** [09:32]
That checkpoint thing is weird too. If last was 1000 and current is 1100, that's exactly interval=100. It should checkpoint.

**@marina.chen** [09:35]
Let me check the `should_checkpoint` function...

**@marina.chen** [09:42]
Found it. The check is `current_seq - last_seq > interval` but it should be `>=`. So at exactly the interval boundary, it skips.

**@sarah.patel** [09:45]
And for the policy thresholds, I'm guessing similar off-by-one issues?

**@james.morrison** [09:48]
Looking at `next_policy`:
```rust
if failure_burst < 1 {
    return ORDER[idx];
}
```
This returns current policy only when failure_burst is 0. When failure_burst is 1, it falls through and escalates. Should be `<= 1` or `< 2`.

**@marina.chen** [09:52]
And `should_deescalate` uses `success_streak > threshold` instead of `>=`. So you need to exceed the threshold, not just meet it.

**@sarah.patel** [09:55]
This explains why our SLA numbers are all over the place. The system is too reactive going up and too sticky coming down.

**@james.morrison** [09:58]
Related: the replay deduplication is also weird. When two events have the same sequence number, I'm seeing inconsistent behavior about which one gets kept.

**@marina.chen** [10:02]
Yeah, the `replay` function uses `>=` for the replace condition, which means on a tie it replaces with the later event in the input array. We want `>` to keep the first occurrence on ties (deterministic replay semantics).

**@devops-bot** [10:05]
:chart: Current policy status: `watch` (45 minutes)
Success streak: 7
Expected status: `normal`

**@sarah.patel** [10:08]
Opening incident ticket. Multiple off-by-one errors in policy and resilience modules causing operational instability.

---

**Thread Summary**:
- Escalation triggers on 1 failure instead of 2+
- De-escalation requires exceeding threshold instead of meeting it
- Checkpoint scheduling off-by-one at interval boundary
- Replay deduplication keeps wrong event on sequence ties

**Affected Files**: `src/policy.rs`, `src/resilience.rs`
