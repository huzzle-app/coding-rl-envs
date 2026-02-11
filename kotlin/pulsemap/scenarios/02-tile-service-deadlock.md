# Incident Report: Map Tile API Deadlock

## Grafana Alert

**Severity**: Critical
**Triggered**: 2024-02-19 14:32 UTC
**Alert Name**: High Request Latency - Tile Service
**Team**: Geospatial Platform

---

## Alert Details

```
CRITICAL: pulsemap-tile-service p99 latency > 30s
Service: tile-service
Endpoint: GET /tiles/{z}/{x}/{y}
Current p99: 45.2s
Threshold: 5s
Duration: 10 minutes
```

## Grafana Dashboard Observations

### Request Latency
```
Metric: http_request_duration_seconds
Endpoint: /tiles/{z}/{x}/{y}

Time         p50      p95      p99
14:00       120ms    450ms    1.2s
14:15       340ms    2.1s     8.4s
14:30       timeout  timeout  timeout
14:32       ALERT FIRED
```

### Thread Pool Metrics
```
Metric: ktor_thread_pool_active_threads
Pool: dispatcher-default

14:00   8/32 threads active
14:15   24/32 threads active
14:30   32/32 threads active (saturated)
14:32   32/32 threads blocked
```

### Coroutine Count
```
Metric: kotlin_coroutines_active

14:00   45 active coroutines
14:15   187 active coroutines
14:30   412 active coroutines (blocked)
14:32   523 active coroutines (all blocked)
```

---

## Timeline

**14:00 UTC** - Normal traffic patterns, latency within SLA

**14:15 UTC** - Marketing campaign launched, 3x increase in map tile requests

**14:25 UTC** - First user reports of "map not loading"

**14:30 UTC** - Thread pool saturated, all threads blocked

**14:32 UTC** - Alert fired, on-call paged

**14:35 UTC** - Emergency pod restart attempted, immediately returned to deadlock state

**14:40 UTC** - Service scaled to 10 replicas, all eventually deadlocked

---

## Thread Dump Analysis

Captured via `jstack` on one of the deadlocked pods:

```
"DefaultDispatcher-worker-1" #31 daemon prio=5 os_prio=0 tid=0x00007f8c14013800 nid=0x47 waiting on condition [0x00007f8c0c7f9000]
   java.lang.Thread.State: WAITING (parking)
    at jdk.internal.misc.Unsafe.park(Native Method)
    - parking to wait for <0x00000000e0c84420> (a kotlinx.coroutines.BlockingCoroutine)
    at kotlinx.coroutines.BlockingCoroutine.joinBlocking(Builders.kt:87)
    at kotlinx.coroutines.BuildersKt__BuildersKt.runBlocking(Builders.kt:59)
    at kotlinx.coroutines.BuildersKt.runBlocking(Unknown Source)
    at com.pulsemap.routes.TileRoutesKt$configureTileRoutes$1$1.invokeSuspend(TileRoutes.kt:34)
    at kotlin.coroutines.jvm.internal.BaseContinuationImpl.resumeWith(ContinuationImpl.kt:33)

"DefaultDispatcher-worker-2" #32 daemon prio=5 os_prio=0 tid=0x00007f8c14014000 nid=0x48 waiting on condition [0x00007f8c0c6f8000]
   java.lang.Thread.State: WAITING (parking)
    at jdk.internal.misc.Unsafe.park(Native Method)
    - parking to wait for <0x00000000e0c84528> (a kotlinx.coroutines.BlockingCoroutine)
    at kotlinx.coroutines.BlockingCoroutine.joinBlocking(Builders.kt:87)
    at kotlinx.coroutines.BuildersKt__BuildersKt.runBlocking(Builders.kt:59)
    ...

[32 more threads with identical stack traces]
```

---

## Internal Slack Thread

**#eng-geospatial** - February 19, 2024

**@sre.kim** (14:35):
> Tile service is completely deadlocked. All dispatcher threads are parked waiting on `runBlocking`. This looks like a classic coroutine deadlock.

**@dev.alex** (14:38):
> Looking at the thread dump... why is there `runBlocking` inside a Ktor route handler? Ktor handlers are already suspend functions!

**@dev.alex** (14:40):
> Found it in `TileRoutes.kt`:
```kotlin
get("/tiles/{z}/{x}/{y}") {
    val tile = runBlocking {  // <-- This is the problem
        tileService.getTile(z, x, y)
    }
    call.respond(tile)
}
```

**@sre.kim** (14:42):
> So every request blocks a thread waiting for a coroutine to complete, but the coroutine needs a thread from the same pool to run?

**@dev.alex** (14:45):
> Exactly. Under low load it works because there are idle threads. But when all threads are occupied by `runBlocking` calls, no thread is available to actually execute the coroutines. Classic thread pool starvation.

**@dev.priya** (14:48):
> I also see a weird pattern in `IngestionService`. Someone used `GlobalScope.launch` for processing incoming sensor data. Those fire-and-forget coroutines aren't tied to any lifecycle.

**@dev.alex** (14:52):
> That explains why we can't gracefully shut down the ingestion service. The coroutines keep running after the server is supposed to stop.

**@dev.priya** (14:55):
> There's also an unbounded channel for the ingestion pipeline:
```kotlin
private val ingestChannel = Channel<SensorReading>(Channel.UNLIMITED)
```
> No backpressure at all. Under burst traffic, memory will grow unbounded.

**@sre.kim** (15:00):
> Memory usage is indeed climbing. We're at 3.2GB on a 4GB pod. Adding to the fix list.

---

## Additional Coroutine Issues Found

### Issue 2: Fire-and-forget GlobalScope

```
2024-02-19T14:47:23.456Z WARN  Shutdown interrupted - 47 orphan coroutines still running
2024-02-19T14:47:23.457Z WARN  GlobalScope coroutine: IngestionService.processReading
2024-02-19T14:47:23.458Z WARN  GlobalScope coroutine: IngestionService.processReading
[45 more lines]
```

### Issue 3: Flow Operator Misuse

```
2024-02-19T14:50:12.789Z DEBUG SpatialAggregationService - Aggregating on: DefaultDispatcher
2024-02-19T14:50:12.790Z DEBUG SpatialAggregationService - Expected dispatcher: Dispatchers.IO
```

The `flowOn` operator appears to not be affecting the upstream dispatcher correctly.

### Issue 4: Async Without Await

```
2024-02-19T14:52:33.123Z DEBUG GeocodingService - Reverse geocode started for: (40.7128, -74.0060)
2024-02-19T14:52:33.456Z DEBUG GeocodingService - Returning address: "Unknown Location"
2024-02-19T14:52:33.789Z DEBUG GeocodingService - Async result available: "350 5th Ave, New York, NY"
```

The geocoding service is returning a fallback value instead of waiting for the actual async result.

---

## Customer Impact

- **Map tiles**: 100% failure rate during incident
- **Users affected**: ~50,000 concurrent users
- **Duration**: 45 minutes until manual intervention
- **Support tickets**: 847 opened during incident

---

## Files to Investigate

Based on thread dumps and logs:
- `src/main/kotlin/com/pulsemap/routes/TileRoutes.kt` - runBlocking inside coroutine
- `src/main/kotlin/com/pulsemap/service/IngestionService.kt` - GlobalScope, unbounded channel
- `src/main/kotlin/com/pulsemap/service/SpatialAggregationService.kt` - flowOn misuse
- `src/main/kotlin/com/pulsemap/service/GeocodingService.kt` - async without await

---

**Status**: INVESTIGATING
**Assigned**: @dev.alex, @dev.priya
**Mitigation**: Emergency restart every 15 minutes (temporary)
**Root Cause**: Coroutine/threading anti-patterns
