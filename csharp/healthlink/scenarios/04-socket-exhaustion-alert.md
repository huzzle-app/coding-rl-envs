# Grafana Alert: Socket Exhaustion and External API Failures

## Alert Configuration

**Alert Name**: HealthLink External API Socket Exhaustion
**Severity**: Warning -> Critical
**Dashboard**: HealthLink Infrastructure Monitoring
**Triggered**: 2024-02-20 14:23 UTC

---

## Alert Details

```
CRITICAL: Outbound TCP connections exhausted
Host: healthlink-api-prod-1.eastus.internal
Metric: node_netstat_Tcp_CurrEstab
Threshold: > 16000 for 5 minutes
Current Value: 16,384 (max)

Additional Alert:
WARNING: High TIME_WAIT socket count
Metric: node_netstat_Tcp_TimeWait
Threshold: > 5000
Current Value: 12,847
```

## Grafana Dashboard Observations

### Socket State Over Time (Last 6 Hours)

```
Time        ESTABLISHED   TIME_WAIT   CLOSE_WAIT
08:00       2,341         1,234       45
10:00       4,892         3,456       89
12:00       8,234         6,789       156
14:00       12,456        9,234       234
14:23       16,384        12,847      312  <- ALERT
```

### External API Response Times

```
Service                         Avg Latency    Error Rate
Insurance Verification API      2,340ms        34.2%
Lab Results API                 1,890ms        28.7%
(baseline expected: <200ms)
```

### Application Error Logs

```
2024-02-20T14:15:23.456Z [ERROR] Insurance verification failed for patient PAT-12345
System.Net.Sockets.SocketException (10048): Only one usage of each socket address (protocol/network address/port) is normally permitted.
   at System.Net.Sockets.Socket.DoConnect(EndPoint endPointSnapshot, SocketAddress socketAddress)
   at System.Net.Http.ConnectHelper.ConnectAsync(String host, Int32 port, CancellationToken cancellationToken)

2024-02-20T14:15:24.789Z [ERROR] Lab results fetch failed for order ORD-67890
System.Net.Http.HttpRequestException: Cannot assign requested address
   at System.Net.Http.HttpConnectionPool.CreateHttp11ConnectionAsync(HttpRequestMessage request, Boolean async, CancellationToken cancellationToken)

2024-02-20T14:15:26.123Z [WARN] HttpClient request timed out
The operation was canceled due to the configured HttpClient.Timeout of 100 seconds elapsing.
```

---

## Service Impact

### Insurance Verification Service

```
Metric: insurance_verification_success_rate
Last 1 hour: 65.8%
Baseline (last 30 days): 99.2%

Error breakdown:
- SocketException: 234 occurrences
- HttpRequestException: 187 occurrences
- TimeoutException: 89 occurrences
```

### Lab Results Integration

```
Metric: lab_results_fetch_success_rate
Last 1 hour: 71.3%
Baseline (last 30 days): 98.7%
```

---

## Internal Slack Thread

**#eng-infra** - February 20, 2024

**@sre.alex** (14:25):
> Socket exhaustion alert firing for healthlink-api-prod-1. We're at max ephemeral ports. External API calls are failing.

**@dev.sarah** (14:32):
> Checking the ExternalApiService. I see `new HttpClient()` being created for every request. That's going to cause socket exhaustion for sure.

**@dev.marcus** (14:35):
> Yeah, `HttpClient` holds sockets in TIME_WAIT state for up to 4 minutes after disposal. If you're creating thousands per minute, you'll run out of ports fast.

**@sre.alex** (14:38):
> Can we just reboot the pods? That'll clear the sockets.

**@dev.marcus** (14:40):
> That's a temporary fix. The sockets will exhaust again within an hour. We need to use `IHttpClientFactory` instead of `new HttpClient()` per request.

**@dev.sarah** (14:45):
> Looking at the code... both `GetInsuranceVerificationAsync` and `GetLabResultsAsync` create new HttpClient instances. This is happening hundreds of times per minute.

**@sre.alex** (14:48):
> Customer complaints coming in. Insurance verification is failing for ~35% of patients right now. Front desk is having to manually call insurance companies.

---

## System Configuration

```
Operating System: Linux (Ubuntu 22.04)
.NET Runtime: 8.0.1
Ephemeral Port Range: 32768-60999 (28,231 ports)
TIME_WAIT timeout: 60 seconds (default)
HttpClient Timeout: 100 seconds
```

## Connection Pool Analysis

```bash
# netstat output from affected pod
$ netstat -ant | awk '{print $6}' | sort | uniq -c | sort -rn
  12847 TIME_WAIT
   3234 ESTABLISHED
    312 CLOSE_WAIT
     89 FIN_WAIT2
     45 SYN_SENT
```

---

## Customer Impact

- **Insurance Verification**: 34.2% failure rate (normally <1%)
- **Lab Results**: 28.7% failure rate (normally <1%)
- **Affected Patients**: ~450 in the last hour
- **Workaround**: Staff calling insurance companies manually

---

## Attempted Mitigations

1. **Pod restart** - Temporary relief, exhaustion recurred within 45 minutes
2. **Horizontal scaling to 5 pods** - Distributed the load but each pod eventually exhausts
3. **Increased socket timeout on OS** - No effect on application behavior

---

## Files to Investigate

Based on error stack traces:
- `src/HealthLink.Api/Services/ExternalApiService.cs` - HttpClient creation pattern
- Check for any other services creating `new HttpClient()` directly

---

**Status**: INVESTIGATING
**Assigned**: @dev.sarah, @sre.alex
**Impact**: High - Patient insurance verification degraded
**Next Check-in**: 15:30 UTC
