# ALERT: Circuit Breaker Cascade Failure - All Services Degraded

**Alert ID**: ALT-2024-031822-001
**Severity**: CRITICAL
**Triggered**: 2024-03-22 03:14:27 UTC
**Source**: prometheus-alertmanager
**Oncall**: @platform-team

---

## Alert Details

```
FIRING: CircuitBreakerCascade
  cluster: prod-us-east-1
  affected_services: gateway, routing, policy, resilience, analytics
  circuit_state: OPEN (all)
  recovery_attempts: 47
  last_success: 2024-03-22 02:58:11 UTC

Description: Multiple services have tripped circuit breakers simultaneously.
Recovery attempts are failing. Cascade failure detected.
```

---

## Metrics Dashboard Snapshot

### Circuit Breaker States (03:14 UTC)
| Service | State | Failures | Threshold | Recovery Attempts |
|---------|-------|----------|-----------|-------------------|
| gateway | OPEN | 5 | 5 | 12 |
| routing | OPEN | 5 | 5 | 8 |
| policy | OPEN | 5 | 5 | 15 |
| resilience | OPEN | 5 | 5 | 7 |
| analytics | OPEN | 5 | 5 | 5 |

### Anomalies Detected

1. **Breaker Trip Threshold**
   - Expected: Trip at 50% failure rate (5/10 = 0.50)
   - Observed: Not tripping at exactly 50%, only at >50%
   - Impact: System tolerates one extra failure before protection kicks in

2. **Recovery Rate Calculation**
   - Metric shows: 30% recovery rate
   - Actual successes: 7 of 10 = 70% success
   - The "recovery rate" appears to be showing failure rate instead

3. **Jitter Not Applied to Backoff**
   - All services retrying at exact same intervals
   - Expected: 800ms +/- 20% jitter
   - Observed: Exactly 800ms, every service, synchronized
   - This causes retry storms and amplifies failures

4. **Half-Open State Not Scaling**
   - Expected: More failures = fewer test requests in half-open
   - Observed: Always allowing exactly 3 requests regardless of history
   - Causing repeated failures during recovery attempts

---

## Log Excerpts

### Gateway Service
```
03:14:22.847 [WARN] CircuitBreaker: failure_rate=0.50, threshold=0.50, tripped=false
03:14:22.848 [INFO] Allowing request through (rate at threshold)
03:14:22.901 [ERROR] Request failed: upstream timeout
03:14:22.902 [WARN] CircuitBreaker: failure_rate=0.55, threshold=0.50, tripped=true
03:14:22.902 [INFO] Circuit OPEN, entering recovery mode
```

### Resilience Service
```
03:14:23.000 [INFO] retry_backoff: attempt=3, base=100ms, computed=800ms
03:14:23.800 [INFO] retry_backoff: attempt=3, base=100ms, computed=800ms
03:14:24.600 [INFO] retry_backoff: attempt=3, base=100ms, computed=800ms
# Note: All three retries at exactly 800ms, no jitter variation
```

### Recovery Monitor
```
03:14:30.000 [INFO] Recovery check: successes=7, total=10
03:14:30.001 [INFO] Recovery rate: 0.30
03:14:30.002 [WARN] Recovery rate below threshold (0.50), staying OPEN
# Note: 7/10 = 0.70, but reporting 0.30 (inverted)
```

---

## Test Failures Related to Alert

```
FAILED: resilience_should_trip
  should_trip_breaker(5, 10, 0.5)
  Expected: true (0.5 >= 0.5)
  Actual: false (using > instead of >=)

FAILED: resilience_jitter
  jitter(100.0, 0.5)
  Expected: value between 50.0 and 150.0
  Actual: exactly 100.0 (no jitter applied)

FAILED: resilience_recovery_rate
  recovery_rate(7, 10)
  Expected: 0.7 (successes/total)
  Actual: 0.3 (failures/total)

FAILED: resilience_half_open_calls
  half_open_max_calls(1) vs half_open_max_calls(10)
  Expected: different values (scaled by failure count)
  Actual: both return 3 (fixed value)

FAILED: resilience_retry_backoff
  retry_backoff(3, 100.0, 10000.0)
  Expected: 800 +/- jitter (range 400-1000)
  Actual: exactly 800.0 (no jitter)
```

---

## Cascade Analysis

The cascade occurred because:

1. **Initial Failure**: Network blip caused 3 failures on routing service
2. **Synchronized Retry**: No jitter meant all clients retried simultaneously
3. **Retry Storm**: 47 clients hit routing at exactly t+800ms
4. **Overload**: Routing service overwhelmed, started failing
5. **Cascade**: Routing failures caused gateway failures
6. **Stuck Recovery**: Inverted recovery rate keeps circuits OPEN

---

## Immediate Actions Taken

- [x] Enabled rate limiting bypass for critical vessel traffic
- [x] Manual circuit breaker override for gateway service
- [x] Disabled automatic retry for non-critical services
- [ ] Root cause fix pending

---

## Business Impact

- Dispatch latency: 340% above SLA
- Vessel queue depth: 892 (normal: <50)
- Customer complaints: 234 tickets in last hour
- Port authority escalation: Singapore, Rotterdam

---

## Affected Components

- `src/resilience.cpp` - circuit breaker, retry backoff, jitter, recovery rate
- All services using resilience patterns

---

## Recommended Fix Areas

1. Threshold comparison in `should_trip_breaker()` - boundary condition
2. Jitter implementation in `jitter()` and `retry_backoff()`
3. Recovery rate calculation in `recovery_rate()`
4. Half-open scaling in `half_open_max_calls()`

---

## References

- Runbook: https://wiki.internal/runbooks/circuit-breaker-cascade
- Dashboard: https://grafana.internal/d/resilience-001
- Related tests: `tests/test_main.cpp` lines 475-543
- PagerDuty: INC-2024-031822
