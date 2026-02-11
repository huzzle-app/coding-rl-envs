# Prometheus Alert: FleetHealthNegative

**Alert Name:** `IronFleetHealthScoreNegative`
**Severity:** critical
**Firing Since:** 2024-03-19T06:22:00Z
**Labels:**
  - `service=ironfleet-analytics`
  - `component=fleet_health`
  - `team=fleet-platform`
  - `env=production`

---

## Alert Rule

```yaml
- alert: IronFleetHealthScoreNegative
  expr: ironfleet_fleet_health_ratio < 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Fleet health metric is negative (impossible value)"
    description: "Fleet health ratio is {{ $value }}, expected range [0.0, 1.0]"
    runbook_url: "https://wiki.internal/runbooks/ironfleet-health-negative"
```

---

## Current Values

```
ironfleet_fleet_health_ratio{region="pacific"} -0.666667
ironfleet_fleet_health_ratio{region="atlantic"} -0.75
ironfleet_fleet_health_ratio{region="centcom"} -0.5
```

---

## Dashboard Snapshot

```
Fleet Health Summary (Last 1h)
------------------------------
Region      | Vessels | Healthy | Reported Health
------------|---------|---------|----------------
Pacific     | 12      | 8       | -66.67%    [!]
Atlantic    | 8       | 6       | -75.00%    [!]
CENTCOM     | 20      | 10      | -50.00%    [!]

Note: Health percentages should be POSITIVE (66.67%, 75%, 50%)
```

---

## Logs from `ironfleet-analytics` Pod

```
2024-03-19T06:15:32Z DEBUG ComputeFleetHealth called vessels=12
2024-03-19T06:15:32Z DEBUG healthy_count=8 total_count=12
2024-03-19T06:15:32Z INFO  fleet_health_computed ratio=-0.666667
2024-03-19T06:15:32Z WARN  health_ratio_anomaly value=-0.666667 expected_range="[0,1]"
```

---

## Test Failures

```
=== FAIL: TestComputeFleetHealthRatio
    analytics_service_test.go:15: health out of range: -0.666667
```

```
=== FAIL: TestHyperMatrix/case_01234
    ... fleet health validation failed: got -0.4, want >= 0
```

---

## Impact Assessment

1. **Dashboards**: Fleet health panels showing impossible negative percentages
2. **Alerting**: Cascading false-positive alerts from downstream monitors
3. **Automation**: Auto-scaling policies treating fleet as 0% healthy, triggering unnecessary failovers
4. **Reporting**: Daily fleet readiness reports contain invalid data

---

## Related Metrics (Also Suspicious)

```
# Channel health scores also negative
ironfleet_channel_health_score{channel="mesh-alpha"} -0.87
ironfleet_channel_health_score{channel="satcom-pri"} -0.45

# Arrival time estimates negative
ironfleet_eta_hours{convoy="BRAVO-7"} -12.5

# Risk scores negative (should be 0.0-1.0)
ironfleet_security_risk_score{zone="alpha"} -0.5
```

---

## Grafana Panel Configuration

The panel expects values in `[0.0, 1.0]` range:
```json
{
  "thresholds": {
    "mode": "absolute",
    "steps": [
      { "color": "red", "value": 0 },
      { "color": "orange", "value": 0.5 },
      { "color": "green", "value": 0.8 }
    ]
  }
}
```

Negative values render as "off the chart" with no color coding.

---

## Possible Causes

- Sign inversion in health calculation
- Division producing negative result
- Return value negated inadvertently

---

## Affected Services

- `services/analytics/service.go` - ComputeFleetHealth
- `services/routing/service.go` - ChannelHealthScore, EstimateArrivalTime
- `services/security/service.go` - ComputeRiskScore

---

## Runbook Actions

1. Check analytics service implementation for sign errors
2. Verify all ratio/score computations return values in expected ranges
3. Run analytics service test suite: `go test -v ./tests/services/...`
4. Validate fix does not break dependent calculations

---

## Escalation

If not resolved within 30 minutes, page Fleet Platform on-call.

**PagerDuty Incident:** PD-2024-8847
