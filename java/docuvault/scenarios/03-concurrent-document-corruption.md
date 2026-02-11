# Customer Escalation: Data Corruption and Thread-Safety Issues

## Zendesk Ticket #58234

**Priority**: Urgent
**Customer**: GlobalTech Industries (Enterprise Tier)
**Account Value**: $180,000 ARR
**CSM**: David Park
**Created**: 2024-01-16 09:45 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We've been experiencing serious data integrity issues with DocuVault over the past two weeks. Our teams are reporting lost document metadata, corrupted version history, and notification failures. This is severely impacting our compliance workflows and we need this resolved immediately.

### Reported Symptoms

1. **Lost Document Changes**: Documents edited by multiple users sometimes lose changes or show stale metadata.

2. **Memory Issues**: Our admin dashboard shows steadily increasing memory usage until the service is restarted.

3. **Notification Failures**: Users report that document share notifications are inconsistent - sometimes they arrive, sometimes they crash the notification system.

4. **Race Condition Errors**: Under heavy load, we see "ConcurrentModificationException" errors in the application logs.

5. **Silent Async Failures**: Background processing jobs for document indexing seem to fail silently without any error logging.

---

## Technical Details from Customer Logs

### Application Logs - Concurrent Modification

```
2024-01-16T08:23:45.123Z ERROR  [notification-worker-3] ConcurrentModificationException during listener notification
java.util.ConcurrentModificationException
    at java.base/java.util.ArrayList$Itr.checkForComodification(ArrayList.java:1013)
    at java.base/java.util.ArrayList$Itr.next(ArrayList.java:967)
    at com.docuvault.service.NotificationService.notifyListeners(NotificationService.java:145)
    at com.docuvault.service.NotificationService.sendDocumentUpdateNotification(NotificationService.java:98)
    at com.docuvault.service.DocumentService.updateDocument(DocumentService.java:234)
```

### Application Logs - Memory Leak Indicators

```
2024-01-16T08:30:00.000Z  INFO  HeapMemoryUsage: used=1.2GB, committed=2.0GB, max=4.0GB
2024-01-16T08:45:00.000Z  INFO  HeapMemoryUsage: used=1.8GB, committed=2.5GB, max=4.0GB
2024-01-16T09:00:00.000Z  INFO  HeapMemoryUsage: used=2.4GB, committed=3.2GB, max=4.0GB
2024-01-16T09:15:00.000Z  INFO  HeapMemoryUsage: used=3.1GB, committed=3.8GB, max=4.0GB
2024-01-16T09:20:00.000Z ERROR  OutOfMemoryError: Java heap space
```

### Thread Dump Analysis

```
"document-processor-1" #47 daemon prio=5 os_prio=0 tid=0x00007f8a8c1a3000 nid=0x2f waiting for monitor entry [0x00007f8a74df9000]
   java.lang.Thread.State: BLOCKED (on object monitor)
    at com.docuvault.security.AuthService.validateToken(AuthService.java:89)
    - waiting to lock <0x00000000c0a8e5f0> (a com.docuvault.security.AuthService)
    at com.docuvault.service.DocumentService.getDocumentWithAuth(DocumentService.java:156)

"document-processor-2" #48 daemon prio=5 os_prio=0 tid=0x00007f8a8c1a4000 nid=0x30 runnable [0x00007f8a74cfa000]
   java.lang.Thread.State: RUNNABLE
    at com.docuvault.security.AuthService.validateToken(AuthService.java:92)
    - locked <0x00000000c0a8e5f0> (a com.docuvault.security.AuthService)
```

### Silent Async Failure Evidence

```
2024-01-16T08:45:12.345Z  INFO  Starting async document indexing for doc_12345
2024-01-16T08:45:12.456Z DEBUG  Submitting indexing task to executor
# Expected: "Indexing completed for doc_12345"
# Actual: No further logs - task silently failed
```

When we added custom exception logging, we saw:
```
2024-01-16T10:30:45.678Z ERROR  Unhandled exception in CompletableFuture
java.util.concurrent.CompletionException: java.lang.NullPointerException: Cannot invoke method on null object
    at java.base/java.util.concurrent.CompletableFuture.encodeThrowable(CompletableFuture.java:315)
    at com.docuvault.service.ShareService.processShareAsync(ShareService.java:178)
```

---

## Internal Slack Thread

**#eng-support** - January 16, 2024

**@david.park** (10:15):
> Hey team, GlobalTech is escalating hard on data corruption issues. They're seeing thread-safety problems and memory leaks. This is their second escalation this month. Can someone take a look urgently?

**@dev.jennifer** (10:22):
> Looking at their thread dump. The AuthService is using `synchronized(this)` but it's marked as prototype-scoped. That means each injection gets a new instance, so the lock is useless!

**@dev.alex** (10:28):
> I see the ConcurrentModificationException too. NotificationService is iterating over a listener list while other threads are modifying it. Classic race condition.

**@dev.jennifer** (10:35):
> Also found the memory leak. DocumentService has a ThreadLocal that's set on every request but never cleared. Each thread in the pool accumulates request contexts indefinitely.

**@dev.alex** (10:42):
> And in VersionService, there's a double-checked locking pattern for caching, but the field isn't `volatile`. That can cause partial object publication on multi-core systems.

**@dev.jennifer** (10:50):
> The async issue is in ShareService. It's using `CompletableFuture.supplyAsync()` but never calling `.exceptionally()` or `.handle()` to catch exceptions. They just vanish.

**@david.park** (10:55):
> How bad is this? Is this affecting all customers?

**@dev.alex** (11:02):
> Technically yes, but it's probabilistic. GlobalTech hits it more because they have high concurrent usage patterns. We should run `mvn test -Dtest="com.docuvault.concurrency.*"` to reproduce.

---

## Reproduction Steps (from QA)

### ThreadLocal Memory Leak
1. Make 1000 requests through a load balancer
2. Monitor heap usage
3. Observe memory growing without bound
4. Force GC - memory not reclaimed

### ConcurrentModificationException
1. Register multiple notification listeners
2. Trigger document updates from 10 concurrent threads
3. Simultaneously add/remove listeners
4. Observe ConcurrentModificationException ~30% of the time

### Synchronized on Prototype Bean
1. Configure AuthService as prototype-scoped (default)
2. Inject AuthService into multiple services
3. Call validateToken() concurrently
4. Observe race conditions in token validation state

**Success Rate**: ~40-60% reproduction rate with concurrent operations

---

## Additional Context

The customer recently deployed DocuVault to their entire legal department (500+ users), which increased their concurrent request volume from ~50/sec to ~300/sec. The issues became noticeable almost immediately after the rollout.

---

## Impact Assessment

- **Users Affected**: ~500 users at GlobalTech Industries
- **Data Loss Risk**: Medium-High - document metadata changes may be silently lost
- **Revenue Risk**: Customer threatening to evaluate alternatives
- **SLA Status**: At risk of breach due to data integrity concerns

---

## Files to Investigate

Based on the stack traces and error patterns:
- `src/main/java/com/docuvault/service/DocumentService.java` - ThreadLocal leak
- `src/main/java/com/docuvault/service/NotificationService.java` - ConcurrentModificationException
- `src/main/java/com/docuvault/service/VersionService.java` - Double-checked locking without volatile
- `src/main/java/com/docuvault/service/ShareService.java` - Silent async failures
- `src/main/java/com/docuvault/security/AuthService.java` - Synchronized on prototype bean

---

**Assigned**: @dev.jennifer, @dev.alex
**Deadline**: EOD January 17, 2024
**Follow-up Call**: Scheduled with customer for January 18, 2024 09:00 PST
