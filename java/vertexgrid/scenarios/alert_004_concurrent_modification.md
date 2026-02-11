# Production Alert - CRITICAL

## Alert Details

**Alert Name**: DispatchListenerConcurrentModificationError
**Severity**: CRITICAL
**First Triggered**: 2024-03-18T08:47:23Z
**Alert Count (24h)**: 847
**Affected Pod(s)**: dispatch-worker-{1,2,3,4,5}

---

## Alert Message

```
CRITICAL: ConcurrentModificationException in dispatch listener notification loop

Service: vertexgrid-dispatch
Method: DispatchService.notifyJobAssigned()
Error Rate: 23.4% of dispatch operations
Impact: Job assignment notifications failing silently

Recent Stack Trace:
java.util.ConcurrentModificationException
    at java.util.ArrayList$Itr.checkForComodification(ArrayList.java:1013)
    at java.util.ArrayList$Itr.next(ArrayList.java:967)
    at com.vertexgrid.dispatch.service.DispatchService.notifyJobAssigned(DispatchService.java:47)
    at com.vertexgrid.dispatch.service.DispatchService.lambda$assignJob$0(DispatchService.java:33)
    at java.util.concurrent.CompletableFuture$AsyncSupply.run(CompletableFuture.java:1768)
```

---

## Metrics Snapshot

```
# HELP dispatch_listener_errors_total Count of listener notification failures
dispatch_listener_errors_total{error="ConcurrentModificationException"} 847

# HELP dispatch_job_notification_success_rate Percentage of successful notifications
dispatch_job_notification_success_rate 0.766

# HELP dispatch_listener_count Current number of registered listeners
dispatch_listener_count 127

# HELP dispatch_jobs_assigned_total Total jobs assigned
dispatch_jobs_assigned_total 3621

# HELP dispatch_async_exceptions_total Async exceptions (may be swallowed)
dispatch_async_exceptions_total 412
```

---

## Error Pattern Analysis

The error occurs when:
1. New dispatch job listeners register during active job processing
2. Multiple dispatch workers process jobs concurrently
3. Load increases during grid balancing events

Error frequency correlates with listener registration rate:

| Listeners Registered/min | Error Rate |
|-------------------------|------------|
| < 5 | 0.1% |
| 5-10 | 3.2% |
| 10-20 | 12.7% |
| > 20 | 23.4% |

---

## Related Issues

### Issue 1: Silent Async Failures

The async notification path appears to swallow exceptions:

```
2024-03-18 08:47:23.445 DEBUG dispatch-worker-3: Assigning job JOB-9847 to vehicle V-102
2024-03-18 08:47:23.447 DEBUG dispatch-worker-3: Job assignment recorded in activeJobs map
[No notification log entry - notification failed silently]
```

When notifications succeed, we should see:

```
2024-03-18 08:47:23.449 INFO dispatch-worker-3: Notified 127 listeners of job JOB-9847 assignment
```

### Issue 2: Listener State Inconsistency

After CME, some listeners receive notification while others don't:

```
Listener audit for JOB-9847:
- GridBalancingListener: NOTIFIED
- LoadForecastListener: NOTIFIED
- DispatchAuditListener: MISSED (CME occurred before reaching)
- ComplianceListener: MISSED
- BillingListener: MISSED
```

---

## Cascade Effects

1. **Grid Balancing**: Load balancing algorithms not receiving dispatch updates
2. **Audit Trail**: Incomplete audit logs for job assignments
3. **Billing**: Dispatch events missing from billing pipeline
4. **Compliance**: Regulatory event logging gaps

---

## Affected Tests

```
DispatchServiceTest.test_concurrent_listener_safe
DispatchServiceTest.test_no_cme_on_iteration
DispatchServiceTest.test_async_exception_handled
DispatchServiceTest.test_completable_future_error
```

---

## Application Logs

```
2024-03-18T08:47:22.123Z INFO  [dispatch-worker-1] Registering new listener: GridRebalanceListener
2024-03-18T08:47:22.234Z INFO  [dispatch-worker-2] Assigning job JOB-9845 to vehicle V-100
2024-03-18T08:47:22.235Z INFO  [dispatch-worker-3] Registering new listener: DemandForecastListener
2024-03-18T08:47:22.236Z INFO  [dispatch-worker-2] Notifying 125 listeners...
2024-03-18T08:47:22.341Z INFO  [dispatch-worker-4] Registering new listener: AncillaryServicesListener
2024-03-18T08:47:22.342Z ERROR [dispatch-worker-2] ConcurrentModificationException during notification
2024-03-18T08:47:22.343Z INFO  [dispatch-worker-1] Assigning job JOB-9846 to vehicle V-101
2024-03-18T08:47:22.445Z INFO  [dispatch-worker-3] Assigning job JOB-9847 to vehicle V-102
[async notification silently fails - no log entry]
```

---

## Runbook Actions Attempted

1. **Increased pod replicas**: No improvement (spreads load but doesn't fix root cause)
2. **Reduced listener registration rate**: Temporary improvement, but not sustainable
3. **Restarted dispatch service**: Clears state but problem recurs within minutes

---

## Investigation Required

1. Review thread safety of listener collection in `DispatchService`
2. Analyze async exception handling in `assignJob()` method
3. Evaluate listener notification iteration pattern
4. Check for proper synchronization during listener registration

---

## Escalation Path

If unresolved within 4 hours:
1. Page on-call Grid Reliability Engineer
2. Consider enabling single-threaded dispatch mode (degraded performance)
3. Notify ISO operations of potential dispatch delays

---

## References

- Grafana Dashboard: https://grafana.vertexgrid.internal/d/dispatch-health
- PagerDuty Incident: PD-2024-18847
- Runbook: https://runbooks.vertexgrid.internal/dispatch-cme
