# Scenario 002: Circuit Breaker Cascade During Partner API Outage

## Slack Thread: #incident-resilience-2024-1203

---

**@sarah.chen** (SRE Lead) - 09:47 AM
@channel We have a P1 in progress. Circuit breakers are not tripping correctly during the Maersk API degradation. Instead of graceful degradation, we're seeing full cascade failures.

---

**@david.kumar** (Backend Engineer) - 09:49 AM
Looking at the CB metrics now. The circuit for maersk-api-gateway hit 5 failures but stayed CLOSED. Shouldn't it have opened?

---

**@sarah.chen** (SRE Lead) - 09:51 AM
That's what I thought. The threshold is set to 5 failures. But the logs show:
```
[09:42:17] failure_count=5, state=CLOSED
[09:42:18] failure_count=6, state=CLOSED
[09:42:19] failure_count=7, state=OPEN
```
It finally opened at failure 7, not 5. Something is off with the boundary check.

---

**@maria.gonzalez** (Platform Architect) - 09:53 AM
I'm also seeing issues with the half-open state. When the CB went to HALF_OPEN after timeout, it let through a flood of requests instead of the expected trickle. We need rate limiting in half-open.

---

**@david.kumar** (Backend Engineer) - 09:56 AM
Found another problem. The checkpoint manager is creating checkpoints at sequence 100, 200, 300... but also at sequence 0. That shouldn't happen - sequence 0 is initialization, not a checkpoint boundary.

---

**@sarah.chen** (SRE Lead) - 10:02 AM
The replay tests are also failing. I'm seeing events with the same id and sequence number but different payloads being deduplicated incorrectly.

Example from the logs:
```ruby
event_a = {id: "ord-123", sequence: 5, payload: {status: "approved"}}
event_b = {id: "ord-123", sequence: 5, payload: {status: "cancelled"}}
# After deduplicate: only event_a retained, event_b lost
```

The dedup key generation isn't accounting for payload differences.

---

**@james.wilson** (QA Lead) - 10:15 AM
Confirmed in test suite. Here are the relevant failures:

```
FAILED: test_circuit_breaker_opens_at_threshold
  Expected state to be 'open' after exactly 5 failures
  Actual: still 'closed'

FAILED: test_half_open_rate_limiting
  Expected: max 1 request in half-open state
  Actual: 47 requests allowed through

FAILED: test_checkpoint_boundary_validation
  Expected: no checkpoint at sequence 0
  Actual: checkpoint recorded

FAILED: test_event_deduplication_with_payload_hash
  Expected: both events retained (different payloads)
  Actual: second event dropped
```

---

**@maria.gonzalez** (Platform Architect) - 10:23 AM
The replay convergence check is also suspect. Running the same events through twice should produce deterministic ordering, but the stability verification seems to be missing.

---

**@sarah.chen** (SRE Lead) - 10:30 AM
Alright team, let's focus on:
1. Circuit breaker threshold boundary condition
2. Half-open state rate limiting
3. Checkpoint creation boundary
4. Deduplication key generation
5. Replay convergence stability

I'm marking this as a resilience module deep-dive. All hands on deck.

---

**@ops-bot** - 10:31 AM
:rotating_light: **Alert**: Customer-facing API latency p99 has exceeded 30s. Downstream services affected: 14.
