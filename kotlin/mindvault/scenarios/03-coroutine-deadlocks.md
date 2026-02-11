# Incident Report: API Timeouts and Unresponsive Endpoints

## PagerDuty Alert

**Severity**: High (P1)
**Triggered**: 2024-02-18 14:23 UTC
**Acknowledged**: 2024-02-18 14:26 UTC
**Team**: Backend Engineering

---

## Alert Details

```
HIGH: mindvault-gateway-prod response time degradation
Host: mindvault-gateway-prod-*.us-east-1
Metric: http_request_duration_seconds_p99
Threshold: >5s for 3 minutes
Current Value: 28.4s (timeout)
Affected Endpoints: /api/v1/documents/*, /api/v1/search/*
```

## Timeline

**14:23 UTC** - Alert triggered for p99 latency exceeding threshold

**14:26 UTC** - On-call acknowledged, observing 502 errors in customer reports

**14:32 UTC** - Identified pattern: requests hang indefinitely, then timeout

**14:45 UTC** - Goroutine/coroutine dump shows thousands of blocked coroutines

**15:10 UTC** - Partial mitigation: increased timeout, but root cause unresolved

## Grafana Dashboard Observations

### Request Latency (Gateway Service)
```
Endpoint                        p50      p99      Timeouts/min
-----------------------------   -----    ------   ------------
GET /api/v1/documents           245ms    28.4s    847
POST /api/v1/documents          312ms    30.0s    623
GET /api/v1/search              189ms    30.0s    1,203
GET /api/v1/embeddings/similar  156ms    30.0s    412
```

### Coroutine Metrics
```
Time      Active Coroutines    Blocked    Completed/sec
-----     -----------------    -------    -------------
14:00     1,247                42         892
14:15     3,891                1,847      234
14:30     8,234                6,102      45
14:45     12,847               11,923     12
```

### Thread Pool Status
```
Pool Name                    Active    Blocked    Queue Size
---------------------------  ------    -------    ----------
Dispatchers.Default          64/64     64         2,847
Dispatchers.IO               128/128   128        4,102
Application-pool             16/16     16         891
```

## Customer Reports

### Enterprise Customer (TechCorp Inc.)

> "Our knowledge management dashboard is completely unusable. Every API call just spins forever. We have 200 users unable to work. This is impacting our quarterly planning meeting TODAY."

### Support Ticket #89234

> "Document upload shows progress to 100% but never completes. After 30 seconds it shows 'Request timeout'. This started happening around 2pm UTC."

## Thread Dump Analysis

### Blocked Coroutine Pattern #1 - Gateway Handlers

```
"DefaultDispatcher-worker-23" BLOCKED
    at kotlinx.coroutines.internal.LockFreeTaskQueueCore.addLast
    at com.mindvault.gateway.routes.DocumentRoutes$documentRoutes$1.invokeSuspend(DocumentRoutes.kt:47)
    - waiting to lock <0x00000007c0a89d30> (kotlinx.coroutines.BlockingCoroutine)

Suspicious: runBlocking{} appears to be called inside a Ktor route handler
```

### Blocked Coroutine Pattern #2 - Background Tasks

```
"DefaultDispatcher-worker-45" RUNNING
    at com.mindvault.gateway.BackgroundProcessor.processQueue(BackgroundProcessor.kt:23)

Note: Coroutine started with GlobalScope.launch - not tied to application lifecycle
Parent coroutine cancelled but child keeps running
```

### Blocked Coroutine Pattern #3 - Document Flow Processing

```
"DefaultDispatcher-worker-12" WAITING
    at com.mindvault.documents.DocumentService.streamDocuments$suspendImpl
    at kotlinx.coroutines.flow.FlowKt__CollectKt.collect

Note: Flow.collect running without timeout wrapper having any effect
ensureActive() not called in collection loop
```

### Blocked Coroutine Pattern #4 - Search Channel

```
"DefaultDispatcher-worker-67" SUSPENDED
    at kotlinx.coroutines.channels.ProducerCoroutine.onSend
    at com.mindvault.search.QueryExecutor.executeQuery

Note: produce{} channel created but consumer stopped reading
Producer suspended indefinitely waiting for buffer space
```

## Mutex Contention Analysis

```
Mutex: GraphService.traversalLock
Holders over time:
    14:23:45.123 - Coroutine #4521 acquired (Dispatchers.Default)
    14:23:45.125 - Coroutine #4521 suspended (IO operation)
    14:23:45.127 - Coroutine #4521 resumed on Dispatchers.Default-worker-8
    14:23:45.128 - Coroutine #4523 waiting for lock
    14:23:45.130 - Coroutine #4521 still holds lock across suspension point

WARNING: Mutex held across dispatcher switch - potential for priority inversion
```

## Embedding Service Failures

```
2024-02-18T14:35:23.456Z [ERROR] Parallel embedding computation failed
kotlinx.coroutines.JobCancellationException: Parent job is Cancelling
    at com.mindvault.embeddings.EmbeddingService.computeBatch

Caused by: java.lang.OutOfMemoryError: unable to create native thread

Note: awaitAll() cancelled all parallel computations when one failed
Expected behavior was partial results, got complete failure
```

## WebSocket Collaboration Issues

```
2024-02-18T14:28:12.789Z [WARN] WebSocket handler exception
io.ktor.websocket.FrameNotProcessedException: Frame was not processed
    at com.mindvault.collab.CollabHandler.handleSession

Note: Late subscribers to SharedFlow see no events
replay = 0 means historical events are lost
```

## CallbackFlow Problems

```
2024-02-18T14:40:56.123Z [DEBUG] CallbackFlow completed immediately
Flow completed without emitting any values
Callback was registered but awaitClose{} not called
External event source never triggered emissions
```

## Attempted Mitigations

1. **Increased timeouts** from 30s to 60s - just delays the inevitable
2. **Restarted gateway pods** - temporary relief for ~5 minutes
3. **Scaled horizontally** - all new pods eventually deadlock too
4. **Disabled background processing** - reduced but didn't eliminate issue

## Questions for Investigation

1. Why are route handlers using blocking constructs that deadlock the event loop?
2. Why are background coroutines not being cancelled when the application shuts down?
3. Why doesn't the timeout wrapper around Flow.collect actually cancel the flow?
4. Why is the Mutex causing priority inversion across suspension points?
5. Why does one failed async computation cancel all siblings instead of returning partial results?

## Impact Assessment

- **Users Affected**: All users (~15,000 active sessions)
- **API Success Rate**: 23% (down from 99.7%)
- **Revenue Impact**: Enterprise customers threatening contract termination
- **SLA Status**: Breached (99.9% availability target)

---

**Status**: INVESTIGATING
**Assigned**: @backend-team, @coroutines-experts
**Follow-up**: Post-incident review scheduled for 2024-02-19 10:00 UTC
