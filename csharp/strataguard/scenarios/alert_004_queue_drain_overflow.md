# Alert: QUEUE-OVERFLOW-CRITICAL

**Alert ID**: ALT-2024-8847
**Severity**: CRITICAL
**Source**: queue-monitor.strataguard.internal
**Triggered**: 2024-11-19 16:33:47 UTC
**Status**: FIRING

---

## Alert Summary

```
ALERT: QueueGuard DrainBatch exceeding batch size limits
SERVICE: dispatch-queue-processor
METRIC: queue.drain.batch_size
THRESHOLD: batchSize parameter
ACTUAL: batchSize + 1 items drained per call
DURATION: 4h 22m (ongoing)
```

## Prometheus Query

```promql
histogram_quantile(0.99,
  rate(strataguard_queue_drain_batch_size_bucket[5m])
) > on() strataguard_queue_drain_batch_limit
```

## Alert Details

The `QueueGuard.DrainBatch()` function is returning **one more item than requested**. When called with `batchSize=3`, it returns 4 items. This off-by-one error is causing:

1. Memory pressure from oversized batches
2. Processing timeouts from larger-than-expected workloads
3. Downstream service overload

## Grafana Dashboard Snapshot

```
Queue Drain Metrics (Last 4 hours)
==================================

Requested Batch Size:  3
Actual Items Drained:  4
Overflow Rate:         100% of drain operations

Memory Usage Trend:
  16:00 UTC: 72% heap
  17:00 UTC: 78% heap
  18:00 UTC: 84% heap
  Current:   89% heap  <-- Approaching OOM threshold

Processing Latency (p99):
  Baseline:  45ms
  Current:   127ms  <-- 182% increase
```

## Stack Trace from OOM Event

```
System.OutOfMemoryException: Exception of type 'System.OutOfMemoryException' was thrown.
   at StrataGuard.QueueGuard.DrainBatch(PriorityQueue queue, Int32 batchSize)
   at StrataGuard.Dispatch.ProcessBatch()
   at StrataGuard.Dispatch.RunLoop()

Heap dump analysis:
  QueueItem[] allocations 34% over budget
  Each drain cycle allocating (batchSize+1) items
```

## Test Failures

```
FAILED: ExtendedTests.DrainBatchExactCount
  Expected: 3 items
  Actual: 4 items
  Message: Assert.Equal() Failure

FAILED: HyperMatrixTests.HyperMatrixCase (queue drain validations)
  Multiple assertions failing on batch size boundaries
```

## Code Under Suspicion

```csharp
// QueueGuard.cs - DrainBatch method
for (var i = 0; i <= batchSize; i++)  // <-- Loop condition suspect
{
    var item = queue.Dequeue();
    if (item == null) break;
    result.Add(item);
}
```

The loop iterates from 0 to `batchSize` **inclusive** (`<=`), which processes `batchSize + 1` iterations instead of `batchSize` iterations.

## Impact Assessment

| Metric | Expected | Actual | Severity |
|--------|----------|--------|----------|
| Batch Size | N | N+1 | HIGH |
| Memory Per Cycle | ~45KB | ~60KB | MEDIUM |
| Processing Time | 45ms p99 | 127ms p99 | HIGH |
| OOM Risk | Low | CRITICAL | CRITICAL |

## Runbook Actions

1. **Immediate**: Reduce batch size parameter by 1 as temporary mitigation
2. **Short-term**: Deploy hotfix for loop boundary condition
3. **Long-term**: Add batch size assertion in drain operation

## Related Alerts

- `ALT-2024-8832`: Memory pressure warning (precursor)
- `ALT-2024-8841`: Processing latency degradation
- `ALT-2024-8845`: Downstream service throttling

## Escalation

```
Paged: @oncall-platform (16:34 UTC)
Acknowledged: @sarah.kim (16:37 UTC)
Status: Investigating
```

---

**Alert Source**: Prometheus + AlertManager
**Dashboard**: https://grafana.strataguard.internal/d/queue-health
**Runbook**: https://wiki.strataguard.internal/runbooks/queue-overflow
