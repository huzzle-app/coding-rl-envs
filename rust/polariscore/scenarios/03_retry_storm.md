# Scenario 03: Retry Storm and Replay Budget Exhaustion

## Incident Type
Slack Escalation / P1 Infrastructure Incident

---

## Slack Thread

**#platform-incidents** at 14:22 UTC

**@sre-oncall**: We're seeing massive CPU spikes on the resilience service cluster. All pods at 95%+ CPU.

**@platform-dev**: Looking at the metrics... retry attempts are through the roof. We're doing 15x normal retry volume.

**@sre-oncall**: Same on the replay budget. Events that should have a budget of ~100 are getting budgets of 500+. We're replaying way more events than we should during recovery.

**@infra-lead**: This started after the network blip at 14:15. Normally we recover gracefully but something's wrong with the backoff curve.

---

## Grafana Dashboard Snapshot

```
Retry Backoff Analysis (14:15 - 14:45 UTC)
==========================================
Attempt 1: Expected 80ms,  Actual 80ms   [OK]
Attempt 2: Expected 160ms, Actual 240ms  [HIGH]
Attempt 3: Expected 320ms, Actual 720ms  [HIGH]
Attempt 4: Expected 640ms, Actual 2160ms [CAPPED]
Attempt 5: Expected 1280ms, Actual 2000ms [CAPPED]

Backoff curve growing faster than 2^n. Hitting cap earlier but
intermediate retries are more aggressive.

Replay Budget Analysis
======================
Events: 140, Timeout: 8s
Expected budget: ~101 events
Actual budget: 239 events  [2.4x OVER]

Events: 500, Timeout: 20s
Expected budget: ~252 events
Actual budget: 532 events  [2.1x OVER]
```

---

## Infrastructure Metrics

```
Time        | Pod CPU | Retry Rate | Replay Events | Error Rate
------------|---------|------------|---------------|------------
14:10 UTC   | 23%     | 1.2k/min   | 85/min        | 0.1%
14:15 UTC   | 45%     | 8.4k/min   | 340/min       | 2.3%
14:20 UTC   | 78%     | 24k/min    | 890/min       | 5.1%
14:25 UTC   | 94%     | 31k/min    | 1.2k/min      | 8.7%
14:30 UTC   | 95%     | THROTTLED  | THROTTLED     | 12.4%
```

---

## Business Impact

- **30-minute partial outage** of resilience services
- **4,200 shipments** delayed during recovery window
- **$89K** in expedited shipping costs to recover SLA
- **Downstream cascade**: Notification service backed up (2.1M queued messages)
- **Customer impact**: 312 customers received delayed tracking updates

---

## Observed Symptoms

1. Retry backoff growing at 3^n instead of 2^n (exponential base too high)
2. Intermediate retry delays are more aggressive than expected
3. Replay budget calculation returning ~2x expected values
4. Budget values appear to be scaled by ~1.9 instead of ~0.9
5. System hits caps earlier but total retry volume still excessive

---

## Affected Test Files

- `tests/resilience_tests.rs` - Retry backoff and replay budget tests
- `tests/chaos_replay_tests.rs` - Integration tests for replay and failover

---

## Relevant Modules

- `src/resilience.rs` - Retry backoff calculation, replay budget, failover logic

---

## Post-Incident Timeline

| Time | Event |
|------|-------|
| 14:15 | Network blip triggers retry storm |
| 14:18 | Alerts fire for high retry rate |
| 14:22 | On-call paged, investigation begins |
| 14:30 | Manual throttling applied |
| 14:45 | Traffic restored with rate limits |
| 15:30 | Backlog cleared, normal operations |

---

## Investigation Questions

1. What exponential base is being used for retry backoff?
2. How is the replay budget multiplier being applied?
3. Is the budget cap calculation correct?
4. Are there cascading effects when resilience is misconfigured?

---

## Resolution Criteria

- Retry backoff must follow 2^n growth pattern
- Replay budget must be bounded correctly
- System must remain stable under network failures
- All resilience tests must pass
