# Grafana Alert: Market Data Service Memory Leak

## Infrastructure Alert

**Severity**: Critical
**Triggered**: 2024-03-20 02:15:00 UTC
**Source**: Prometheus/Grafana
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: market-data-prod memory usage exceeds threshold
Host: qc-market-data-prod-1.us-east-1.internal
Container: market-feed-service
Memory Usage: 14.2 GB / 16 GB (88.75%)
Memory Growth Rate: +450 MB/hour
Projected OOM: ~4 hours

Tokio Runtime Stats:
  Active Tasks: 47,829
  Spawned (lifetime): 892,341
  Completed: 844,512
  Leaked: ~47,829 (estimated)
```

## Memory Growth Timeline

```
Time        Memory    Active Tasks    Subscriptions
----------------------------------------
00:00 UTC   2.1 GB    1,247          342
01:00 UTC   3.8 GB    8,923          2,891
02:00 UTC   7.2 GB    24,567         8,234
02:15 UTC   14.2 GB   47,829         15,892
```

## Grafana Dashboard Observations

### Task Count Growth

The number of active Tokio tasks is growing unboundedly:

```
Metric: tokio_spawned_tasks_total
Rate: ~800 tasks/minute (new spawns)

Metric: tokio_completed_tasks_total
Rate: ~780 tasks/minute (completions)

Net growth: ~20 tasks/minute that never complete
```

### Subscription Metrics

```
Metric: market_feed_subscriptions_active
Time: 02:15 UTC

Symbols with active subscriptions: 892
Average subscribers per symbol: 17.8
Orphaned subscriptions (no receivers): 4,234

Note: "Orphaned subscriptions" are feeds with no active receivers
but the background task is still running.
```

### Quote Staleness

Several symbols are reporting stale quotes despite feed being "active":

```
Symbol    Last Quote    Staleness    Status
----------------------------------------------
AAPL      02:14:59      16 sec       STALE
MSFT      02:15:00      15 sec       STALE
GOOGL     02:10:23      5 min        VERY STALE
TSLA      02:08:45      7 min        VERY STALE
AMZN      01:55:12      20 min       DEAD
```

## Task Dump Analysis

Sampling active tasks at 02:15 UTC:

```
Task #47823 [RUNNING for 3h 47m]
  spawn location: market/src/feed.rs:83
  state: sleeping (tokio::time::sleep)
  note: No receivers subscribed

Task #47824 [RUNNING for 3h 45m]
  spawn location: market/src/feed.rs:83
  state: sleeping (tokio::time::sleep)
  note: No receivers subscribed

Task #47825 [RUNNING for 3h 42m]
  spawn location: market/src/feed.rs:83
  state: sleeping (tokio::time::sleep)
  note: broadcast channel send returned Err (no receivers)

... (pattern repeats for ~47,000 tasks)
```

## Log Analysis

```
2024-03-20T01:45:23Z WARN  market::feed: No receivers for AAPL
2024-03-20T01:45:24Z WARN  market::feed: No receivers for AAPL
2024-03-20T01:45:25Z WARN  market::feed: No receivers for AAPL
2024-03-20T01:45:26Z WARN  market::feed: No receivers for AAPL
... (message repeats indefinitely)

Note: The warning is logged but the task continues running instead of stopping
```

## Reproduction Steps

Engineering was able to reproduce locally:

```bash
# Start market feed service
cargo run --bin market-feed

# Subscribe to quotes (simulating client)
wscat -c ws://localhost:8006/quotes/AAPL

# Disconnect client (Ctrl+C)
# Observe: Background task continues running
# Memory continues to grow

# Repeat subscribe/disconnect cycle 100 times
# Memory usage: 2GB+ with no active clients
```

## Customer Impact

- **Quote latency**: Increasing due to memory pressure
- **Stale data**: Some symbols showing minutes-old quotes
- **Service degradation**: GC pauses causing latency spikes
- **Impending outage**: OOM kill expected within hours

## Internal Slack Thread

**#platform-oncall** - March 20, 2024

**@oncall.kim** (02:17):
> Market data service is at 88% memory and climbing. Going to OOM in a few hours.

**@sre.alex** (02:20):
> What's with the task count? 47k active tasks seems way too high.

**@oncall.kim** (02:22):
> Looking at the task spawns... they're all from market/src/feed.rs line 83. That's where we spawn the quote generator loop.

**@dev.jordan** (02:25):
> Oh no. I see the issue. When `tx.send(quote).is_err()` returns error (no receivers), we just log a warning and continue. We never break the loop.

**@sre.alex** (02:27):
> So every time a client disconnects, we leave a zombie task running forever?

**@dev.jordan** (02:28):
> Exactly. And the `stop()` function sets an atomic bool, but the tasks don't actually check it. They just keep sleeping and trying to send.

**@oncall.kim** (02:30):
> Can we restart the service?

**@sre.alex** (02:31):
> We can, but all the zombie tasks will just accumulate again. Need a real fix.

**@dev.jordan** (02:35):
> There's also the issue that when we call `start_symbol_feed()`, we spawn a new task but never track the handle. We have no way to cancel it.

---

## Questions for Investigation

1. Why doesn't the feed loop break when there are no receivers?
2. Why isn't the `running` atomic flag being checked?
3. How do we cancel spawned tasks when they're no longer needed?
4. Why isn't there a cleanup mechanism for orphaned subscriptions?

## Files to Investigate

Based on the task spawn locations:
- `services/market/src/feed.rs` - Task spawning and lifecycle
- Any code related to subscription management and cleanup

## Mitigations Attempted

1. **Increase memory**: Temporary relief, just delays OOM
2. **Rolling restart**: Clears memory but tasks re-accumulate
3. **Rate limit new subscriptions**: Reduces growth rate but doesn't fix leak

---

**Status**: INVESTIGATING
**Assigned**: @platform-team
**Workaround**: Scheduled restarts every 4 hours until fix deployed
