# ALERT: Anomalous Health Scores Triggering False Positives

**Alert ID:** MON-2024-0322-7841
**Severity:** Warning
**Source:** Prometheus/Alertmanager
**First Triggered:** 2024-03-22 03:17:42 UTC
**Times Triggered (24h):** 847

---

## Alert Configuration

```yaml
- alert: TensorForgeServiceUnhealthy
  expr: tensorforge_health_score < 0.7
  for: 5m
  labels:
    severity: warning
    team: platform
  annotations:
    summary: "Service {{ $labels.service }} health score below threshold"
    description: "Health score is {{ $value }} (threshold: 0.7)"
```

## Alert Pattern Analysis

The alerting system is generating spurious health alerts for services that are operating normally. Investigation reveals the health score calculation is weighting metrics incorrectly.

### Sample Alert Instances

```
[FIRING] TensorForgeServiceUnhealthy
  service: inference-dispatcher
  health_score: 0.52
  availability: 0.99
  performance: 0.35

[FIRING] TensorForgeServiceUnhealthy
  service: model-registry
  health_score: 0.48
  availability: 0.98
  performance: 0.30
```

## Root Cause Hypothesis

The `health_score` function should weight availability at 60% and performance at 40%, but appears to have the weights swapped:

```
Expected: health_score = availability * 0.6 + performance * 0.4
          = 0.99 * 0.6 + 0.35 * 0.4
          = 0.594 + 0.14
          = 0.734 (HEALTHY)

Observed: health_score = availability * 0.4 + performance * 0.6
          = 0.99 * 0.4 + 0.35 * 0.6
          = 0.396 + 0.21
          = 0.606 -> rounds to 0.52 with other factors (UNHEALTHY)
```

## Additional Telemetry Anomalies

During investigation, the following related issues were discovered:

### 1. Error Rate Calculation Inverted

```
[2024-03-22T03:21:15.442Z] telemetry::metrics DEBUG
  total_requests=10000
  errors=50
  computed_error_rate=200.0
  EXPECTED: 0.005 (50/10000)
  ANOMALY: Appears to be computing total/errors instead of errors/total
```

### 2. Throughput Using Wrong Time Unit

```
[2024-03-22T03:22:08.117Z] telemetry::throughput DEBUG
  request_count=5000
  duration_ms=60000
  computed_throughput=0.083
  EXPECTED: 83.33 req/sec (5000 / 60 seconds)
  ANOMALY: Computing per-millisecond instead of per-second
```

### 3. Alert Threshold Logic Inverted

```
[2024-03-22T03:25:33.892Z] telemetry::alerting DEBUG
  metric=cpu_utilization
  value=0.95
  threshold=0.80
  should_alert=false
  EXPECTED: true (0.95 > 0.80 should trigger)
  ANOMALY: Using < instead of > for threshold comparison
```

### 4. Uptime Calculation Showing Downtime Percentage

```
[2024-03-22T03:28:41.223Z] telemetry::uptime DEBUG
  total_seconds=86400
  downtime_seconds=3600
  computed_uptime_pct=4.17
  EXPECTED: 95.83% ((86400-3600)/86400 * 100)
  ANOMALY: Computing downtime percentage instead of uptime
```

## Impacted Tests

- `test_health_score_weights_availability_higher` - Weight ordering
- `test_error_rate_fraction_of_total` - Division direction
- `test_throughput_per_second` - Time unit conversion
- `test_alert_triggers_above_threshold` - Comparison operator
- `test_uptime_percentage_calculation` - Formula correctness
- `test_metric_within_tolerance` - Tolerance check logic
- `test_aggregate_metrics_returns_average` - Aggregation returns sum instead
- `hyper_matrix_scenarios::telemetry_*` - Observability matrix

## Operational Impact

| Issue | Impact |
|-------|--------|
| False health alerts | On-call fatigue, 847 spurious pages in 24h |
| Inverted error rate | Dashboards show 200x actual error rate |
| Wrong throughput | Capacity planning data unusable |
| Missed alerts | Real issues may not trigger alerts |
| Inverted uptime | SLA reports showing 4% uptime instead of 96% |

## Grafana Dashboard Anomalies

The following panels are showing incorrect data:

1. **Service Health Overview** - All services showing degraded (yellow/red)
2. **Error Rate Trend** - Showing 20,000% error rate
3. **Throughput Graph** - Showing 0.08 req/sec instead of 83 req/sec
4. **Uptime SLA** - Showing 4.17% instead of 95.83%

## Recommended Actions

1. Review telemetry module for mathematical errors
2. Check weight assignments in health scoring
3. Verify division direction in rate calculations
4. Confirm comparison operators in alerting logic
5. Test uptime formula with known values

## Silence Window

Temporary silence applied to `TensorForgeServiceUnhealthy` alerts until fix deployed:

```bash
amtool silence add alertname="TensorForgeServiceUnhealthy" \
  --duration=24h \
  --comment="False positives due to VHB107-114 bugs"
```

---

**Runbook:** [Telemetry Troubleshooting](internal://runbooks/telemetry-debug)
**Escalation:** #platform-oncall
**Next Review:** 2024-03-22 12:00 UTC
