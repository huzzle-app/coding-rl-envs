# Grafana Alert: Notification Service Memory Leak

## Alert Details

**Alert Name**: NotificationService Memory Growth
**Severity**: Critical
**Firing Since**: 2024-02-22 14:32 UTC
**Dashboard**: EventHorizon Infrastructure > Notifications

---

## Alert Configuration

```yaml
alert: NotificationServiceMemoryGrowth
expr: |
  rate(process_memory_rss_bytes{service="notifications"}[5m]) > 10000000
for: 10m
labels:
  severity: critical
annotations:
  summary: "Notification service memory growing unbounded"
  description: "Memory increased by {{ $value | humanize }}B in last 5 minutes"
```

## Current Metrics

| Metric | Value | Normal Range |
|--------|-------|--------------|
| Memory RSS | 3.8 GB | 200-400 MB |
| GC Gen2 Collections | 847 | ~50/hour |
| Managed Heap | 2.9 GB | 100-200 MB |
| Large Object Heap | 1.2 GB | <50 MB |
| Event Handlers Registered | 127,431 | ~1,000 |

---

## Incident Timeline

**08:00 UTC** - Deployment of v3.2.4 (includes new "ticket purchase confirmation" notifications)

**09:15 UTC** - Memory at 450MB (normal post-startup)

**11:30 UTC** - Memory at 1.2GB, first GC pressure warning

**13:00 UTC** - Memory at 2.4GB, response times degrading

**14:32 UTC** - Alert fires, memory at 3.8GB

**14:45 UTC** - Pod restarted by Kubernetes OOM killer

**14:47 UTC** - New pod starts at 180MB, memory growth immediately resumes

---

## User Impact

### Slack Thread: #ops-escalations

**@cs-lead** (14:15):
> Getting reports from users that real-time notifications have stopped working. Purchase confirmations not showing up in the app even though orders went through.

**@mobile-dev** (14:22):
> SignalR connections keep dropping. We're seeing constant reconnection attempts in the mobile app logs.

**@ops-alex** (14:35):
> Notification service pods are being OOM killed. Memory usage is through the roof. Looking into it now.

---

## Memory Profile Analysis

### dotnet-dump Analysis

```
> dumpheap -stat

Statistics:
      MT    Count    TotalSize Class Name
...
7ff8a2341230   127,431   8,155,584 System.EventHandler`1[[System.String]]
7ff8a2341458    89,234   2,855,488 EventHorizon.Notifications.Services.NotificationService+<>c__DisplayClass4_0
7ff8a2341690    89,234   1,427,744 System.Action`1[[System.String]]
...

Total 847,234 objects, 2.9GB
```

### GC Roots Analysis

```
> gcroot 0x00007ff8a2341230

Thread 4823:
    ESP: 000000E4F59FE850
        -> 0x00000213a8c12340 EventHorizon.Notifications.Services.NotificationService
        -> 0x00000213a8c12360 System.EventHandler`1[[System.String]] (OnNotificationSent)
        -> 0x00000213a8c12380 System.Object[] (invocation list)
            -> 127,431 delegates registered

Found 1 unique root.
```

---

## Code Investigation Notes

### Notification Service Event Pattern

The notification service exposes a public event that other components subscribe to:

```csharp
public class NotificationService : INotificationService
{
    public event EventHandler<string>? OnNotificationSent;

    public async Task SendAsync(string userId, string message)
    {
        // ... send notification ...
        OnNotificationSent?.Invoke(this, message);
    }
}
```

### SignalR Hub Subscriptions

The SignalR hub appears to subscribe to this event on every client connection:

```
Log snippet from NotificationHub:
2024-02-22T09:15:23Z DEBUG Client connected connectionId=abc123
2024-02-22T09:15:23Z DEBUG Subscribing to notification events for user=user456
2024-02-22T09:15:23Z DEBUG Client connected connectionId=def456
2024-02-22T09:15:23Z DEBUG Subscribing to notification events for user=user789
...
```

There's no corresponding "unsubscribe" log on client disconnect.

---

## Async Stream Behavior

We also noticed issues with the notification streaming endpoint:

```http
GET /api/notifications/stream HTTP/1.1
Accept: text/event-stream
Authorization: Bearer <token>
```

When clients disconnect (close browser, lose network), the server-side stream continues running indefinitely:

```
2024-02-22T14:30:15Z DEBUG Streaming notifications for user=user123
2024-02-22T14:30:16Z DEBUG Streaming notifications for user=user123
2024-02-22T14:30:17Z DEBUG Streaming notifications for user=user123
...
[Connection was closed at 14:30:15, but logs continue]
```

### goroutine (Thread) Count Analysis

```
Time: 14:30 UTC
Managed Thread Count: 3,847
Active IAsyncEnumerable Streams: 2,341
Abandoned Streams (no client): ~2,100

Note: Streams continue producing even after client disconnect
```

---

## Related Issues

### Message Queue Ordering

QA reported intermittent test failures in the notification ordering tests:

```
Expected: ["first", "second", "third"]
Actual:   ["first", "third", "second"]

Test: NotificationOrderingTest.ShouldPreserveFIFOOrder
Failure rate: ~15% (non-deterministic)
```

The message queue is supposed to maintain strict FIFO ordering, but messages sent in rapid succession sometimes arrive out of order.

---

## Questions for Investigation

1. **Event handler leak**: Are subscribers unsubscribing when clients disconnect?
2. **Async stream lifecycle**: How are IAsyncEnumerable streams cancelled when clients disconnect?
3. **Cancellation token propagation**: Is the CancellationToken being checked in streaming methods?
4. **Message timestamp resolution**: Why do messages sent in quick succession get reordered?

---

## Reproduction Steps

1. Start the Notifications service
2. Connect 100 SignalR clients
3. Disconnect 90 clients (simulate browser close)
4. Observe memory - should return to baseline but doesn't
5. Check event handler count - still shows all 100 subscriptions

---

## Attempted Mitigations

1. **Increased memory limit** - Pod limit raised to 4GB, just delayed OOM
2. **Forced GC** - Called `GC.Collect()` via admin endpoint, no effect (objects still rooted)
3. **Rolling restart** - Memory immediately starts growing again after restart

---

## Services to Investigate

- `Notifications` - Event subscription pattern, stream lifecycle
- `Notifications.Hubs` - SignalR connection management

## Key Files

- `NotificationService.cs` - Event handler implementation
- `NotificationHub.cs` - SignalR hub connection handling
- `MessageQueue.cs` - Message ordering implementation

---

**Status**: INVESTIGATING
**Assigned**: @notifications-team
**Escalation**: Platform Engineering team notified
