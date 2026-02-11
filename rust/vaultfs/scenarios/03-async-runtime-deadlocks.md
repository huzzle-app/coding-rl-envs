# Customer Escalation: Service Freezes Under Load

## Zendesk Ticket #82451

**Priority**: Urgent
**Customer**: TechNova Solutions (Enterprise Tier)
**Account Value**: $180,000 ARR
**CSM**: David Chen
**Created**: 2024-02-16 11:45 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> Our development team has been experiencing critical issues with VaultFS over the past 3 days. The service becomes completely unresponsive during peak usage hours. We've had to restart the VaultFS pods multiple times a day. This is severely impacting our CI/CD pipelines and developer productivity.

### Reported Symptoms

1. **Complete Service Freeze**: API stops responding to all requests (not just slow, completely frozen)

2. **Upload Operations Hang**: File uploads get stuck at various percentages and never complete

3. **Notification Delivery Stops**: Real-time sync notifications stop working, then the entire service dies

4. **High CPU Despite No Progress**: CPU pegged at 100% but no requests are completing

---

## Technical Details from Customer Logs

### Application Logs (Kubernetes pod)

```
2024-02-16T09:15:22Z INFO  Processing upload request id=upload_abc123
2024-02-16T09:15:22Z INFO  Acquiring file lock for exclusive access...
2024-02-16T09:15:22Z DEBUG Lock manager: requesting lock_a
2024-02-16T09:15:22Z DEBUG Lock manager: acquired lock_a, now requesting lock_b
2024-02-16T09:15:22Z INFO  Processing upload request id=upload_def456
2024-02-16T09:15:22Z DEBUG Lock manager: requesting lock_b
2024-02-16T09:15:22Z DEBUG Lock manager: acquired lock_b, now requesting lock_a
[NO MORE LOG OUTPUT - Service frozen]
```

### Thread Dump (tokio-console capture)

```
Task 1842 [BLOCKED 847s]:
  at src/services/lock_manager.rs:67 - waiting on Mutex
  spawned at src/handlers/upload.rs:45

Task 1843 [BLOCKED 847s]:
  at src/services/lock_manager.rs:72 - waiting on Mutex
  spawned at src/handlers/upload.rs:45

Task 1850 [BLOCKED 412s]:
  at src/services/storage.rs:134 - std::thread::sleep (BLOCKING!)
  spawned at src/handlers/files.rs:89

Task 1851-2847 [BLOCKED varying]:
  at various locations - all waiting on blocked tasks
```

### Client-Side Errors

```
2024-02-16T09:17:00Z ERROR Connection timeout after 30s: POST /api/v1/files/upload
2024-02-16T09:17:30Z ERROR Connection timeout after 30s: GET /api/v1/files/abc123
2024-02-16T09:18:00Z ERROR Connection reset by peer: WebSocket /api/v1/sync
```

---

## Internal Slack Thread

**#eng-escalations** - February 16, 2024

**@david.chen** (11:50):
> TechNova is on fire again. Complete service freeze, third time this week. They're threatening to evaluate alternatives. Need eyes on this ASAP.

**@dev.sarah** (12:05):
> Looking at their logs. The lock acquisition pattern is classic deadlock - two tasks each holding one lock and waiting for the other. Check lock_manager.rs lines 65-75.

**@dev.marcus** (12:12):
> Found another issue. In storage.rs, there's a `std::thread::sleep()` call in an async function. That blocks the entire tokio executor thread, not just the task.

**@dev.sarah** (12:18):
> That would explain the cascade. One blocked executor thread = all tasks scheduled on that thread are stuck. Combined with the deadlock, the whole service grinds to a halt.

**@dev.marcus** (12:25):
> Also looking at upload.rs - the upload handler returns a Future that's not Send because it holds a reference to a non-Send type across an await point. That might be causing the "cannot move between threads" panics they mentioned.

**@sre.kim** (12:30):
> We're also seeing the notification service crash separately:
```
thread 'tokio-runtime-worker' panicked at 'called `Result::unwrap()` on an `Err` value: RecvError'
    at src/services/notification.rs:89
```

**@dev.sarah** (12:35):
> The channel sender is getting dropped somewhere, and the receiver is unwrapping the error. Classic pattern - sender dropped = channel closed = receiver gets error.

**@dev.marcus** (12:40):
> Root causes I'm seeing:
> 1. Deadlock from nested lock acquisition in different orders
> 2. Blocking call (std::thread::sleep) inside async context
> 3. Non-Send future crossing await boundary
> 4. Channel receiver unwrapping instead of handling sender drop

**@david.chen** (12:45):
> How widespread is this? Just TechNova or everyone?

**@sre.kim** (12:50):
> Theoretically all customers, but TechNova hits it more because they have high concurrent upload volume. Their CI system does 50+ parallel uploads during build peaks.

---

## Reproduction Steps (from QA)

1. Start VaultFS with default configuration
2. Initiate 20+ concurrent file uploads
3. Observe service becoming unresponsive within 2-3 minutes
4. Check task traces - deadlocked tasks visible
5. Attempt any API request - hangs indefinitely

**Success Rate**: 80%+ reproduction with concurrent uploads

---

## Resource Monitoring During Incident

| Metric | Normal | During Freeze |
|--------|--------|---------------|
| CPU Usage | 15-25% | 100% (single core) |
| Memory | 512MB | 480MB (stable) |
| Active Connections | 50-100 | 2000+ (queued) |
| Completed Requests/min | 500+ | 0 |
| Tokio Tasks (blocked) | 0-5 | 500+ |

---

## Questions for Investigation

1. What lock ordering is causing the deadlock?
2. Why is there a blocking sleep call in async code?
3. What non-Send type is being held across the await point?
4. Why is the notification channel sender being dropped prematurely?

---

## Files to Investigate

Based on stack traces and log patterns:
- `src/services/lock_manager.rs` - Deadlock in lock acquisition
- `src/services/storage.rs` - Blocking call in async context
- `src/handlers/upload.rs` - Non-Send future issue
- `src/services/notification.rs` - Channel receiver panic

---

**Assigned**: @dev.sarah, @dev.marcus
**Deadline**: EOD February 17, 2024
**Customer Call**: Scheduled for February 18, 2024 10:00 PST
