# ALERT: Gateway Service Performance Degradation and Request Failures

**Alert ID:** ALT-2024-1847
**Severity:** Warning -> Critical (escalated)
**Source:** Prometheus/Grafana
**First Triggered:** 2024-11-20 16:45 UTC
**Current Status:** FIRING

---

## Alert Rules Triggered

| Alert | Threshold | Current Value | Duration |
|-------|-----------|---------------|----------|
| `gateway_request_latency_p99` | > 2000ms | 8,450ms | 4h 15m |
| `gateway_error_rate_5xx` | > 1% | 23.7% | 3h 42m |
| `gateway_thread_pool_exhausted` | > 0 | 847 events | 2h 18m |
| `gateway_coroutine_leak_detected` | > 100 | 12,847 active | 4h 15m |

---

## Grafana Dashboard Snapshot

```
Gateway Health - Last 6 Hours
================================

Request Rate:          ████████████░░░░ 2,847 req/s (normal: 3,200)
Error Rate (5xx):      ████████████████ 23.7% (threshold: 1%)
P99 Latency:           ████████████████ 8,450ms (SLO: 200ms)
Active Coroutines:     ████████████████ 12,847 (baseline: 200)
Thread Pool Util:      ████████████████ 100% SATURATED

Memory Usage:          ████████████████ 7.2GB / 8GB (90%)
CPU Usage:             ████████████░░░░ 78%
```

---

## Error Patterns from Logs

### Pattern 1: Deadlock in Document Fetch (43% of errors)

```
2024-11-20T18:22:14.234Z ERROR [gateway] --- Timeout after 30000ms
    Route: GET /api/documents/{id}
    Cause: kotlinx.coroutines.TimeoutCancellationException
    Stack trace:
        at kotlinx.coroutines.BlockingCoroutine.joinBlocking(Builders.kt:85)
        at kotlinx.coroutines.BuildersKt__BuildersKt.runBlocking(Builders.kt:59)
        at com.helixops.gateway.GatewayService$configureRoutes$1.invoke(GatewayService.kt:19)

    Note: runBlocking detected inside suspend context - potential deadlock
```

### Pattern 2: Double Response Error (28% of errors)

```
2024-11-20T18:23:45.891Z ERROR [gateway] --- IllegalStateException
    Route: GET /api/health
    Message: Response has already been sent
    Stack trace:
        at io.ktor.server.response.ApplicationResponseKt.respondText(ApplicationResponse.kt:45)
        at com.helixops.gateway.GatewayService$configureRoutes$2.invoke(GatewayService.kt:28)
```

### Pattern 3: Coroutine Leak (Background Tasks)

```
2024-11-20T18:15:00.000Z WARN [gateway] --- Orphaned coroutine detected
    Coroutine: StandaloneCoroutine{Active}@7f8a9b2c
    Parent: GlobalScope
    Created: 2024-11-20T14:30:00.000Z
    Duration: 3h 45m (still running)

    Note: 847 similar orphaned coroutines from GlobalScope.launch
```

### Pattern 4: Cancellation Not Propagated

```
2024-11-20T18:45:22.567Z WARN [gateway] --- CancellationException swallowed
    StatusPages handler caught CancellationException
    This breaks structured concurrency - request should have been cancelled
    Returned 500 instead of proper cancellation handling
```

---

## Security Scanner Alerts

The security scanner also flagged potential vulnerabilities in the gateway:

```
[SECURITY] SQL Injection vulnerability detected
    Route: GET /api/search?q=...
    Risk: User input directly interpolated into SQL query
    Example: q='; DROP TABLE documents; --

[SECURITY] Path Traversal vulnerability detected
    Route: GET /api/files/{path...}
    Risk: No validation against directory traversal
    Example: /api/files/../../../etc/passwd

[SECURITY] SSRF vulnerability detected
    Route: POST /api/webhooks/test
    Risk: Arbitrary URL fetch without validation
    Example: http://169.254.169.254/metadata (AWS metadata)
```

---

## Test Suite Failures

```bash
./gradlew :gateway:test

GatewayTests > testNoRunBlockingInHandler FAILED
GatewayTests > testSingleResponsePerRequest FAILED
GatewayTests > testCoroutineScopedToApplication FAILED
GatewayTests > testCancellationExceptionRethrown FAILED
GatewayTests > testSqlInjectionPrevention FAILED
GatewayTests > testPathTraversalBlocked FAILED
GatewayTests > testSsrfProtection FAILED
```

---

## Kubernetes Pod Status

```
NAME                        READY   STATUS    RESTARTS   AGE
gateway-7b9f8c6d4-x2k9m    1/1     Running   12         4h    (OOMKilled x3)
gateway-7b9f8c6d4-p8n3w    1/1     Running   8          4h    (OOMKilled x2)
gateway-7b9f8c6d4-q1j5v    0/1     CrashLoop 15         4h

Events:
  Warning  OOMKilled  4m ago   Container exceeded memory limit (8Gi)
  Warning  Unhealthy  2m ago   Liveness probe failed: connection refused
```

---

## Thread Dump Analysis

```
"ktor-dispatcher-worker-1" BLOCKED
    waiting for monitor entry at kotlinx.coroutines.BlockingCoroutine.joinBlocking

"ktor-dispatcher-worker-2" BLOCKED
    waiting for monitor entry at kotlinx.coroutines.BlockingCoroutine.joinBlocking

... (all 200 worker threads blocked)

"GlobalScope-worker-847" RUNNING
    at com.helixops.gateway.GatewayService$startBackgroundTasks$1.invokeSuspend
```

---

## Impact Assessment

- **Availability:** Service degraded, 23.7% of requests failing
- **Latency:** P99 at 8.4 seconds (42x above SLO)
- **Security:** Multiple injection vulnerabilities active
- **Resources:** Thread pool exhausted, memory near limit

---

## Recommended Investigation Areas

1. Why is `runBlocking` being used inside Ktor route handlers?
2. Why are multiple responses being sent for single requests?
3. Why are background tasks not tied to application lifecycle?
4. Why is `CancellationException` being caught in error handlers?
5. Review input validation for security-sensitive routes

---

## Escalation Path

- 16:45 UTC: Alert triggered, auto-assigned to on-call
- 17:30 UTC: Escalated to senior engineer
- 18:00 UTC: Security team notified of injection vulnerabilities
- 19:00 UTC: Incident commander engaged

**Current Assignee:** @platform-team
**Next Escalation:** VP Engineering at 20:00 UTC if unresolved
