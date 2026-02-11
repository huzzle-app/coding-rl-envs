# Incident Report INC-2024-001

## Incident Summary
**Severity**: P1 - Critical
**Status**: Open
**Duration**: Ongoing (intermittent)
**Affected Service**: VertexGrid Dispatch Optimization Engine
**Impact**: Continental load balancing operations halted during peak demand windows

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 2024-03-15 14:23 | Grid dispatch optimization requests begin queuing |
| 2024-03-15 14:27 | First timeout alert from load balancer health checks |
| 2024-03-15 14:31 | Operations team observes dispatch API returning 504 Gateway Timeout |
| 2024-03-15 14:35 | All 8 dispatch worker threads show 100% CPU, zero throughput |
| 2024-03-15 14:42 | Emergency restart of dispatch service restores operation |
| 2024-03-15 18:47 | Incident recurs during evening peak load balancing |

---

## Symptoms

1. **API Timeouts**: The `/api/v1/dispatch/optimize` endpoint stops responding after approximately 10 seconds of high concurrency.

2. **Thread Starvation**: JVM thread dump shows all ForkJoinPool worker threads in WAITING state:
   ```
   "ForkJoinPool.commonPool-worker-1" waiting on java.util.concurrent.ForkJoinTask
   "ForkJoinPool.commonPool-worker-2" waiting on java.util.concurrent.ForkJoinTask
   "ForkJoinPool.commonPool-worker-3" waiting on java.util.concurrent.ForkJoinTask
   [... all 8 common pool threads blocked ...]
   ```

3. **No Exceptions**: Application logs show no errors or exceptions during the hang. Operations simply stop.

4. **Load Correlation**: Incident occurs when the number of pending dispatch jobs exceeds ~50 and available generation units exceeds ~8.

---

## Business Impact

- **Grid Imbalance Risk**: Unable to dispatch generation resources to meet demand fluctuations
- **Load Shedding**: 3 regions entered manual load shedding protocols
- **Financial Exposure**: Estimated $47,000/hour in balancing market penalties
- **SLA Breach**: Continental dispatch latency SLA (< 5 seconds) violated for 23 minutes cumulative

---

## Affected Tests

The following tests are failing or timing out:

```
DispatchServiceTest.test_no_parallel_stream_deadlock
DispatchServiceTest.test_forkjoin_not_starved
TrackingServiceTest.test_parallel_speed_calculation_completes
```

---

## Thread Dump Analysis

Stack trace captured during incident (abbreviated):

```
"ForkJoinPool.commonPool-worker-1" #47 daemon prio=5 WAITING
   at java.base/jdk.internal.misc.Unsafe.park(Native Method)
   at java.base/java.util.concurrent.ForkJoinPool.awaitWork(ForkJoinPool.java:1893)
   at java.base/java.util.concurrent.ForkJoinPool.scan(ForkJoinPool.java:1854)
   at com.vertexgrid.dispatch.service.DispatchService.lambda$optimizeAssignments$1(DispatchService.java:68)
   at java.base/java.util.stream.ReferencePipeline$3$1.accept(ReferencePipeline.java:197)
   at java.base/java.util.Spliterators$ArraySpliterator.forEachRemaining(Spliterators.java:992)
   at java.base/java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:234)
   [... nested parallel stream invocation ...]
```

---

## Metrics

```
dispatch_optimization_duration_seconds{quantile="p99"}: TIMEOUT
dispatch_active_jobs_count: 67
dispatch_available_vehicles: 12
forkjoin_pool_active_thread_count: 8
forkjoin_pool_queued_task_count: 847
```

---

## Hypothesis

The dispatch optimization algorithm appears to be blocking under high concurrency. Thread dumps suggest nested parallel processing may be exhausting the shared thread pool, but the exact mechanism is unclear.

---

## Investigation Requested

1. Review the `DispatchService.optimizeAssignments()` method for potential blocking patterns
2. Analyze thread pool utilization during parallel stream operations
3. Evaluate whether nested parallelism could cause resource starvation

---

## References

- Prometheus Dashboard: https://grafana.vertexgrid.internal/d/dispatch-health
- Thread Dump Archive: /var/log/vertexgrid/threaddumps/2024-03-15T14_35_00Z.txt
- Related: TrackingService has similar parallel processing patterns that may also be affected
