# Incident Report: Distributed System Failures During Region Failover

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-18 03:15 UTC
**Duration**: 2 hours 45 minutes
**Team**: Platform Engineering

---

## Alert Cascade

```
03:15 UTC - CRITICAL: consul_leader_elections_per_minute > 10
03:16 UTC - CRITICAL: distributed_lock_timeout_rate > 5%
03:17 UTC - WARNING: event_processing_lag > 30 seconds
03:18 UTC - CRITICAL: split_brain_detected service=transcode
03:19 UTC - CRITICAL: duplicate_transcodes_detected
03:22 UTC - CRITICAL: event_ordering_violations > 100
```

## Incident Summary

During scheduled maintenance of our us-east-1 region, a network partition caused our distributed coordination systems to fail in unexpected ways. Multiple services experienced split-brain scenarios, duplicate work execution, and event ordering violations.

---

## Timeline

**03:00 UTC** - Maintenance window begins for us-east-1 network equipment

**03:12 UTC** - Network latency between us-east-1 and us-west-2 spikes to 500ms

**03:15 UTC** - Consul leader election starts flapping between regions

**03:17 UTC** - transcode-service in us-east-1 believes it's the leader
- transcode-service in us-west-2 ALSO believes it's the leader
- Both start processing the same job queue

**03:20 UTC** - Distributed locks start timing out
- Operations that normally take 2 seconds are exceeding 5-second lock timeout
- Locks released prematurely, concurrent modifications occurring

**03:25 UTC** - Event processing becomes inconsistent
- Events arriving out of order
- Duplicate events being processed (idempotency failing)
- Event projections corrupted

**03:45 UTC** - Network connectivity restored

**04:00 UTC** - Services still in inconsistent state due to corrupted event store

**05:30 UTC** - Manual intervention to reconcile state, services recovered

---

## Symptoms Observed

### 1. Leader Election Split-Brain

Both datacenters believed they had the leader for transcode-service:

**us-east-1 logs:**
```
03:17:22Z INFO [leader-election] Acquired leadership for transcode-service
03:17:23Z INFO [transcode] Starting job processor as leader
03:17:24Z INFO [transcode] Processing job job-7834921
```

**us-west-2 logs (SAME TIME):**
```
03:17:22Z INFO [leader-election] Acquired leadership for transcode-service
03:17:23Z INFO [transcode] Starting job processor as leader
03:17:24Z INFO [transcode] Processing job job-7834921  <-- SAME JOB
```

Result: Same video transcoded twice, stored with conflicting metadata.

### 2. Distributed Lock Failures

```
03:22:15Z ERROR Lock acquisition timeout: upload-session-abc123
03:22:15Z WARN  Proceeding without lock (fallback behavior)
03:22:16Z ERROR Lock acquisition timeout: upload-session-abc123
03:22:16Z WARN  Proceeding without lock (fallback behavior)
03:22:18Z ERROR Concurrent modification detected: upload-session-abc123
```

Upload sessions being modified by multiple workers simultaneously.

### 3. Event Ordering Violations

```
Expected event sequence:
  1. VideoUploadStarted (t=1000)
  2. VideoChunkReceived (t=1001)
  3. VideoChunkReceived (t=1002)
  4. VideoUploadCompleted (t=1003)

Actual processed order:
  1. VideoUploadStarted (t=1000)
  2. VideoUploadCompleted (t=1003)  <-- out of order!
  3. VideoChunkReceived (t=1001)
  4. VideoChunkReceived (t=1002)
```

Projections built from events showed incomplete uploads as complete.

### 4. Idempotency Key Collisions

```
03:25:01.234Z [event-bus] Processing event: video.uploaded idempKey=video.uploaded-1708229101234
03:25:01.234Z [event-bus] Processing event: video.uploaded idempKey=video.uploaded-1708229101234
03:25:01.235Z [event-bus] Duplicate detected, skipping  <-- WRONG!
```

Different events with same timestamp generated identical idempotency keys, causing valid events to be dropped.

---

## Internal Slack Thread

**#incident-20240218** - February 18, 2024

**@sre-alex** (03:25):
> We have split-brain in transcode. Both regions think they're leader.

**@eng-priya** (03:28):
> Looking at the Consul session config... the session behavior is set to `release` instead of `delete`. That means when the session expires, the lock is released but not deleted, allowing another node to grab it without proper handoff.

**@sre-alex** (03:32):
> Lock timeouts are also way too aggressive. Default is 5 seconds, but with 500ms network latency, any operation taking more than 4.5 seconds times out.

**@eng-david** (03:35):
> Found the event ordering issue. We're using RabbitMQ topic exchange but not including sequence numbers. With network delays, events from us-east-1 arrive after us-west-2 events even though they happened earlier.

**@eng-priya** (03:40):
> The idempotency keys are just `${eventType}-${timestamp}`. Under load, we get multiple events with same millisecond timestamp. They're treated as duplicates when they're actually different events.

**@sre-alex** (03:45):
> Network is back but the damage is done. We have:
> - 847 duplicate transcode jobs
> - 1,234 event ordering violations
> - 23 corrupted upload sessions
> - Event projections are inconsistent

**@eng-david** (04:00):
> The leader election watch is silently failing. When Consul connection drops, the error handler does nothing. Node thinks it's still leader even after losing Consul connectivity.

---

## Technical Analysis

### Leader Election Flaws

1. **Session Behavior**: Uses `release` instead of `delete`, allowing stale leaders
2. **No Fencing Tokens**: No monotonic token to detect stale leaders
3. **Silent Watch Failures**: Watch error handler is empty, failures go unnoticed
4. **Short TTL**: 10-second TTL causes flapping under network delays

### Distributed Lock Flaws

1. **Clock Skew**: Lock expiration based on local time, not synchronized
2. **Too Short Timeout**: 5-second default insufficient for cross-region operations
3. **Non-Atomic Release**: Check-then-delete race condition in release logic
4. **No Fencing**: Operations don't verify lock is still held before completing

### Event Sourcing Flaws

1. **No Sequence Numbers**: Events have timestamps but no monotonic sequence
2. **Weak Idempotency**: Key = type + timestamp (high collision probability)
3. **No Gap Detection**: Missing events don't trigger alerts
4. **Unbounded Memory**: Processed event set grows without bounds

---

## Metrics During Incident

```
Leader Elections Per Minute:
  Normal: 0-1
  During incident: 47 (flapping between regions)

Lock Acquisition Failures:
  Normal: <0.1%
  During incident: 34%

Event Processing Lag:
  Normal: <100ms
  During incident: 45 seconds

Duplicate Event Rate:
  Normal: <0.01%
  During incident: 12%
```

---

## Impact Assessment

- **Duplicate Work**: 847 videos transcoded twice (wasted compute: ~$2,400)
- **Data Corruption**: 23 upload sessions in inconsistent state
- **User Impact**: ~5,000 users saw incorrect video status
- **Recovery Time**: 2 hours 45 minutes manual intervention

---

## Files to Investigate

- `shared/utils/index.js` - DistributedLock, LeaderElection
- `shared/events/index.js` - EventBus, idempotency, ordering
- Clock skew handling in distributed operations
- Consul session configuration

---

**Status**: RESOLVED (with data reconciliation)
**Post-Mortem**: Scheduled 2024-02-21
**Follow-up Actions**:
1. Implement fencing tokens for leader election
2. Add sequence numbers to events
3. Increase lock timeout for cross-region operations
4. Add proper error handling for Consul watch
