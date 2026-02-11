# Incident Report: Matching Engine Frozen in Production

## PagerDuty Alert

**Severity**: Critical (P0)
**Triggered**: 2024-03-15 14:23:17 UTC
**Acknowledged**: 2024-03-15 14:24:02 UTC
**Team**: Trading Systems Engineering

---

## Alert Details

```
CRITICAL: matching-engine-prod order processing halted
Host: qc-matching-prod-1.us-east-1.internal
Metric: order_processing_rate
Threshold: <100 orders/sec for 30 seconds
Current Value: 0 orders/sec
Duration: 2 minutes 17 seconds
```

## Timeline

**14:23:17 UTC** - Initial alert: Order processing rate dropped to zero

**14:23:45 UTC** - Second matching engine node (qc-matching-prod-2) also frozen

**14:24:12 UTC** - Customer complaints flooding in: "My order is stuck"

**14:25:00 UTC** - Attempted failover to standby matching engine - also froze within 30 seconds

**14:26:30 UTC** - Emergency pod restart initiated
```
kubectl delete pod qc-matching-prod-1 --force
Result: New pod started, began processing, froze again after 47 seconds
```

**14:28:00 UTC** - All three matching engine instances now frozen

## Grafana Dashboard Observations

### Order Latency Profile
```
Metric: order_match_latency_p99
Time: 14:20 - 14:30 UTC

14:20  12ms
14:21  15ms
14:22  18ms
14:23  847ms
14:23:17  TIMEOUT (>30s)
14:23:30  TIMEOUT
... continues indefinitely
```

### Thread/Task State
```
Metric: tokio_runtime_active_tasks
Time: 14:23:17 UTC (snapshot during freeze)

Active tasks: 1,247
Blocking tasks: 4
Tasks waiting on mutex: 4 (unusual - normally 0-1)
```

### Order Book State
```
Symbol: AAPL
Bid depth: 147 orders
Ask depth: 203 orders
Last match: 14:23:16.892 UTC
Next match: NEVER (frozen)
```

## Thread Dump Analysis

When the freeze occurred, we captured a thread dump. Several threads appear to be waiting on locks:

```
Thread "tokio-runtime-worker-3" [BLOCKED]
  at parking_lot::mutex::Mutex::lock
  at quantumcore::matching::engine::MatchingEngine::submit_order (engine.rs:77)
  - waiting to acquire: order_book lock for "AAPL"
  - holding: risk_state lock for account "ACC-12345"

Thread "tokio-runtime-worker-7" [BLOCKED]
  at parking_lot::mutex::Mutex::lock
  at quantumcore::matching::engine::MatchingEngine::update_risk_and_cancel (engine.rs:111)
  - waiting to acquire: risk_state lock for account "ACC-12345"
  - holding: order_book lock for "AAPL"
```

## Reproduction Pattern (from QA)

The freeze seems to occur when these conditions are met:
1. High order volume (>500 orders/sec)
2. Concurrent order submissions and cancellations for the same account
3. Multiple symbols involved simultaneously

**Reproduction steps:**
1. Submit 100 orders for account ACC-12345 on symbol AAPL
2. Simultaneously cancel all orders for ACC-12345 on AAPL
3. Repeat 5-10 times
4. System freezes ~60% of the time

## Customer Impact

- **Orders affected**: ~2,300 orders stuck in limbo
- **Accounts affected**: 847 active traders
- **Estimated losses**: Unknown - some customers missed market moves
- **SLA breach**: Yes - 99.99% uptime guarantee violated

## Internal Slack Thread

**#trading-incidents** - March 15, 2024

**@oncall.maya** (14:25):
> Matching engine is completely frozen. All orders stuck. Already tried restart.

**@lead.james** (14:27):
> Thread dump shows two threads waiting on each other. Classic deadlock pattern.

**@oncall.maya** (14:28):
> But we use parking_lot mutexes - aren't those supposed to handle this?

**@lead.james** (14:30):
> Mutexes don't magically prevent deadlocks. If two threads acquire locks in opposite order, they'll still deadlock. Look at the stack traces - one has order_book then risk_state, the other has risk_state then order_book.

**@dev.sarah** (14:32):
> I see it in the code. `submit_order` grabs order_book first, then risk. But `update_risk_and_cancel` grabs risk first, then order_book. When both run concurrently...

**@lead.james** (14:33):
> Boom. Deadlock. We need consistent lock ordering across all code paths.

**@oncall.maya** (14:35):
> Rolling back to last week's release as emergency mitigation.

---

## Questions for Investigation

1. Why are locks being acquired in different orders in different functions?
2. Are there other code paths with inconsistent lock ordering?
3. Should we use a single lock instead of per-resource locks?
4. Can we detect this pattern with static analysis or tests?

## Relevant Logs

```
2024-03-15T14:23:16.892Z INFO  Matched order order_id="ORD-78234" price=185.50 qty=100
2024-03-15T14:23:16.894Z DEBUG Acquiring order book lock symbol="AAPL"
2024-03-15T14:23:16.894Z DEBUG Acquired order book lock symbol="AAPL"
2024-03-15T14:23:16.895Z DEBUG Acquiring risk state lock account="ACC-12345"
... (no more logs - system frozen)
```

## Files to Investigate

Based on stack traces, focus on:
- `services/matching/src/engine.rs`
- Any code that acquires both order_book and risk_state locks

---

**Status**: RESOLVED (rollback to v2.3.4)
**Root Cause**: Pending investigation
**Assigned**: @trading-team
**Follow-up**: Post-incident review scheduled for 2024-03-16 10:00 UTC
