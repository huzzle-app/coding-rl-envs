# Incident Report: Memory Exhaustion and Thread Starvation

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-08 14:32 UTC
**Acknowledged**: 2024-02-08 14:35 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: fleetpulse-dispatch-prod-1 OOMKilled
Host: fleetpulse-dispatch-prod-1.us-east-1.internal
Metric: container_memory_working_set_bytes
Threshold: >95% for 3 minutes
Exit Code: 137 (OOMKilled)
```

## Concurrent Alerts

Within 10 minutes of the initial alert:

```
14:32 - CRITICAL: dispatch-prod-1 OOMKilled
14:35 - WARNING: tracking-prod-2 high CPU usage (98%)
14:38 - CRITICAL: gateway-prod-1 thread pool exhausted
14:41 - WARNING: notifications-prod-3 memory at 87%
14:44 - CRITICAL: dispatch-prod-2 OOMKilled
```

## Timeline

**14:32 UTC** - Dispatch service pod 1 OOM killed

**14:35 UTC** - Alert acknowledged. JFR (Java Flight Recorder) snapshot captured from dispatch pod 2

**14:38 UTC** - Gateway service stops accepting new requests
```
java.util.concurrent.RejectedExecutionException:
Thread pool 'asyncExecutor' exhausted (max=200, active=200, queued=5000)
```

**14:41 UTC** - Tracking service shows 98% CPU, mostly in ForkJoinPool

**14:44 UTC** - Dispatch pod 2 also OOM killed

**14:50 UTC** - Team deploys temporary fix: increase memory limits from 4Gi to 8Gi

**15:02 UTC** - Memory filling up again, now at 6Gi and climbing

## JFR Analysis: Dispatch Service

### Thread Dump Summary
```
Total threads: 847
  - ForkJoinPool.commonPool: 412 threads (all WAITING or BLOCKED)
  - async-executor: 200 threads (all RUNNABLE)
  - pool-1-thread-*: 156 threads (various states)
  - kafka-consumer: 48 threads
  - remaining: 31 threads (main, GC, etc.)
```

### Hot Methods (CPU Sampling)
```
72.3%  java.util.stream.AbstractPipeline.evaluate
  └── 68.1%  ForkJoinPool.commonPool-worker (various)
       └── 45.2%  com.fleetpulse.dispatch.service.OptimizationService.optimizeRoutes
            └── nested parallelStream() calls

15.4%  java.util.concurrent.CompletableFuture.get
  └── 12.1%  com.fleetpulse.dispatch.service.DispatchService.findBestVehicle
       └── waiting on never-completing futures

8.2%   java.lang.Object.wait
```

### Memory Allocation (Heap Snapshot)
```
Top Allocators:
  42% - char[] arrays (String concatenation in loops)
  23% - com.fleetpulse.dispatch.model.Assignment[]
  18% - java.util.ArrayList (backing arrays)
  12% - kafka-consumer buffers
   5% - other
```

## Application Logs

### Dispatch Service
```
14:30:12.445 INFO  Starting route optimization for fleet=continental-transport
14:30:12.446 DEBUG Vehicles to optimize: 450
14:30:12.447 DEBUG Using parallel stream for outer loop
14:30:12.448 DEBUG Using parallel stream for inner distance calculations
14:30:12.449 DEBUG ForkJoinPool.commonPool available parallelism: 11
14:30:12.450 DEBUG Submitting 450 * 450 = 202,500 parallel tasks
...
14:32:01.123 WARN  ForkJoinPool tasks timing out
14:32:05.234 ERROR Task waited more than 30s for ForkJoinPool slot
14:32:10.345 ERROR OutOfMemoryError: unable to create native thread
```

### Gateway Service
```
14:38:01.001 INFO  Async request received: /api/v1/dispatch/optimize
14:38:01.002 DEBUG Delegating to @Async method
14:38:01.003 WARN  Thread pool 'asyncExecutor' queue size: 4500
14:38:01.234 ERROR RejectedExecutionException: Task rejected from asyncExecutor
14:38:01.235 DEBUG @Async proxy attempting internal call...
14:38:01.236 WARN  Method call did not go through proxy - executing synchronously
```

### Notifications Service
```
14:40:15.001 DEBUG Publishing notification to channel: dispatch-alerts
14:40:15.002 DEBUG Acquiring lock on channel name: "dispatch-alerts".intern()
14:40:15.003 WARN  Lock contention detected - 47 threads waiting
14:40:15.234 WARN  Lock contention detected - 89 threads waiting
14:40:15.567 ERROR Lock acquisition timeout after 5000ms
```

### Tracking Service
```
14:35:23.001 INFO  Processing GPS update batch: 12,000 positions
14:35:23.002 DEBUG Sorting positions by timestamp
14:35:23.003 DEBUG Using Collectors.toMap for timestamp indexing
14:35:23.004 ERROR IllegalStateException: Duplicate key 2024-02-08T14:35:22.123Z
java.lang.IllegalStateException: Duplicate key 2024-02-08T14:35:22.123Z
    at java.util.stream.Collectors.duplicateKeyException
    at java.util.stream.Collectors.lambda$uniqKeysMapAccumulator$1
```

## Heap Dump Analysis

### String Concatenation Issue
```
Top retained objects by size:
1. char[1048576] - 42MB (CSV export buffer, created by repeated +=)
2. char[524288]  - 21MB (another CSV buffer)
3. char[262144]  - 11MB (report generation)
...
Pattern: String concatenation in loops creating O(n^2) intermediate arrays
```

### ThreadLocal Leak
```
Instances of RequestContext: 2,847
  - Expected: ~200 (thread pool size)
  - Actual: 2,847 (never removed from ThreadLocal)
  - Each instance retains: ~15KB of request data
  - Total leak: ~42MB and growing
```

### Weak vs Soft Reference Cache
```
Analytics cache hit rate: 12%
  - Expected: 85%+
  - Cause: WeakReference cache entries collected under memory pressure
  - Log evidence: "Cache miss for vehicle-stats-fleet-123 (entry was null)"
```

## Kubernetes Resource Metrics

```
┌─────────────────────┬──────────┬──────────┬─────────────┐
│ Pod                 │ CPU Req  │ CPU Use  │ Memory Use  │
├─────────────────────┼──────────┼──────────┼─────────────┤
│ dispatch-prod-1     │ 2 cores  │ 11 cores │ 7.8Gi/8Gi   │
│ dispatch-prod-2     │ 2 cores  │ 9 cores  │ 7.2Gi/8Gi   │
│ tracking-prod-1     │ 1 core   │ 4 cores  │ 3.1Gi/4Gi   │
│ gateway-prod-1      │ 1 core   │ 2 cores  │ 2.8Gi/4Gi   │
│ notifications-prod-1│ 0.5 core │ 1.5 cores│ 1.9Gi/2Gi   │
└─────────────────────┴──────────┴──────────┴─────────────┘
```

## Customer Impact

- Dispatch optimization requests timing out after 60s
- Vehicle assignments delayed by 5-15 minutes
- Push notifications not being delivered
- Real-time tracking updates laggy (30s+ delay)

## Questions for Investigation

1. Why is the ForkJoinPool starving? Are we nesting parallel streams?
2. Why are CompletableFutures never completing?
3. Why is @Async not working for some methods (proxy bypass)?
4. Why are notifications using String.intern() as a lock?
5. What's causing the ThreadLocal leak in the gateway?
6. Why is the analytics cache returning null so often?

## Files to Investigate

Based on the symptoms:
- `dispatch/src/main/java/com/fleetpulse/dispatch/service/OptimizationService.java`
- `dispatch/src/main/java/com/fleetpulse/dispatch/service/DispatchService.java`
- `gateway/src/main/java/com/fleetpulse/gateway/filter/RequestContextFilter.java`
- `notifications/src/main/java/com/fleetpulse/notifications/service/ChannelManager.java`
- `analytics/src/main/java/com/fleetpulse/analytics/cache/VehicleStatsCache.java`
- `tracking/src/main/java/com/fleetpulse/tracking/service/PositionAggregator.java`

---

**Status**: MITIGATED (memory increased, but root cause unfixed)
**Assigned**: @platform-team, @performance-team
**Follow-up**: Memory limits are a band-aid - need proper fix within 48 hours
