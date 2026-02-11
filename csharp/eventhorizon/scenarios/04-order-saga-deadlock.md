# Support Escalation: Orders Stuck in Processing State

## Zendesk Ticket #ESC-29847

**Priority**: Urgent
**Category**: Order Processing
**Created**: 2024-03-14 11:23 UTC
**Customer**: Enterprise Account - LiveNation Partnership

---

## Customer Report

### Initial Ticket

> We're experiencing a critical issue with bulk ticket purchases. We use the EventHorizon API to process large batches of corporate ticket allocations.
>
> Starting this morning, approximately 30% of our orders get stuck in "Processing" status and never complete. The tickets are locked (unavailable for other buyers) but the orders never finalize.
>
> This is blocking $450K worth of corporate sales for the upcoming Bruno Mars tour.

### Follow-up (2 hours later)

> The problem is getting worse. Now we're seeing:
> - Orders stuck indefinitely
> - No error messages returned
> - API calls that never return (timeout after 30 seconds)
> - Tickets remain reserved but orders don't complete
>
> We've tried:
> - Retrying stuck orders (makes it worse)
> - Smaller batch sizes (same issue)
> - Different time windows (same issue)
>
> Please escalate immediately.

---

## Engineering Investigation

### Slack Thread: #incident-response

**@sre-maya** (12:15):
> Got an urgent escalation from the LiveNation account. Looking at the Orders service metrics now.

**@sre-maya** (12:22):
> Found it - we have a thread contention issue. Look at these metrics:

```
Orders Service - Thread Pool Stats
Time: 12:20 UTC

Threads Blocked: 847
Threads Running: 12
Thread Pool Queue: 3,241 pending items
Avg Task Wait Time: 28.4 seconds

SemaphoreSlim Wait Stats:
  _lock1 waiters: 423
  _lock2 waiters: 424
```

**@backend-dev** (12:28):
> That's a deadlock pattern. Let me check the saga implementation...

**@backend-dev** (12:35):
> Found the issue. We have two operations that acquire locks in opposite orders:

```
Operation A: acquire _lock1 -> acquire _lock2
Operation B: acquire _lock2 -> acquire _lock1

When A and B run concurrently, they can deadlock.
```

**@sre-maya** (12:38):
> That matches what I'm seeing. The stuck orders all have both a saga execution and a compensation running simultaneously.

---

## Order State Analysis

```sql
SELECT
    order_id,
    status,
    created_at,
    updated_at,
    saga_state,
    compensation_state
FROM orders
WHERE status = 'Processing'
  AND updated_at < NOW() - INTERVAL '5 minutes'
ORDER BY created_at;
```

Results:
```
| order_id     | status     | saga_state  | compensation_state | stuck_duration |
|--------------|------------|-------------|--------------------|----------------|
| ORD-a1b2c3d4 | Processing | Executing   | Compensating       | 47 minutes     |
| ORD-e5f6g7h8 | Processing | Executing   | Compensating       | 45 minutes     |
| ORD-i9j0k1l2 | Processing | Executing   | Compensating       | 43 minutes     |
| ... (847 rows stuck in this state)                                              |
```

---

## Thread Dump Analysis

Captured via `dotnet-dump`:

```
Thread 0x1a3f (blocked):
  at System.Threading.SemaphoreSlim.WaitAsync()
  at EventHorizon.Orders.Services.OrderSagaService.ExecuteSagaAsync()
  -- Waiting to acquire _lock2, already holding _lock1 --

Thread 0x1a42 (blocked):
  at System.Threading.SemaphoreSlim.WaitAsync()
  at EventHorizon.Orders.Services.OrderSagaService.CompensateAsync()
  -- Waiting to acquire _lock1, already holding _lock2 --

[Pattern repeats 423 times]
```

---

## Reproduction Scenario

The deadlock occurs when:

1. Customer creates order (triggers `ExecuteSagaAsync`)
2. Payment times out
3. System automatically triggers `CompensateAsync` for rollback
4. If both run on overlapping time windows, deadlock occurs

Test that reliably reproduces:

```csharp
// This test hangs indefinitely
[Fact]
public async Task ConcurrentSagaAndCompensation_ShouldNotDeadlock()
{
    var saga = new OrderSagaService();
    var orderId = "test-order";

    var executeTask = saga.ExecuteSagaAsync(orderId);
    var compensateTask = saga.CompensateAsync(orderId);

    // This never completes due to deadlock
    await Task.WhenAll(executeTask, compensateTask);
}
```

---

## Fire-and-Forget Processing Issue

Additionally, we found that order processing errors are being silently swallowed:

```
2024-03-14T11:45:23Z INFO  Processing order ORD-xyz123
2024-03-14T11:45:24Z DEBUG Starting internal processing
[No further logs for this order - error was thrown but not observed]
```

When examining the order:
```sql
SELECT * FROM orders WHERE order_id = 'ORD-xyz123';
-- Status still shows 'Pending', never transitioned to 'Processing' or 'Failed'
```

The fire-and-forget pattern means exceptions in order processing are never observed or logged.

---

## Business Impact

| Metric | Value |
|--------|-------|
| Stuck Orders | 847 |
| Locked Ticket Value | $1.2M |
| Affected Customers | 312 |
| Support Tickets | 89 |
| Revenue at Risk | $450K (LiveNation alone) |

---

## Related: Async Void Consumer Pattern

We also noticed a pattern in the MassTransit consumer logs:

```
2024-03-14T12:00:15Z INFO  Received OrderCreated event orderId=ORD-abc
2024-03-14T12:00:15Z DEBUG Consumer started processing
[No completion log - async void consumer]

2024-03-14T12:00:16Z ERROR Unobserved task exception: Order not found
```

The error appears in the global unobserved exception handler, not in the consumer error handling, suggesting the consumer method signature might be `async void` instead of `async Task`.

---

## Questions for Investigation

1. **Lock ordering**: Why do `ExecuteSagaAsync` and `CompensateAsync` acquire locks in different orders?
2. **Deadlock detection**: Can we add timeout or deadlock detection to the semaphores?
3. **Fire-and-forget**: Why are processing tasks not being awaited?
4. **Error observation**: How do we ensure exceptions in background tasks are properly logged?

---

## Temporary Mitigations Applied

1. **12:45 UTC** - Disabled automatic compensation (manual rollback only)
2. **13:00 UTC** - Restarted Orders service to clear stuck threads
3. **13:15 UTC** - Added 1-hour TTL to order locks to auto-release stuck tickets

---

## Services to Investigate

- `Orders` - Saga orchestration, lock management
- `Orders.Services` - `OrderSagaService`, `OrderService`

## Key Patterns to Review

- SemaphoreSlim usage and lock ordering
- Fire-and-forget async patterns
- MassTransit consumer method signatures
- Task.Run and exception observation

---

**Status**: INVESTIGATING
**Assigned**: @orders-platform-team
**Customer Communication**: Account manager notified, hourly updates promised
