# INC-001: Model Inference Requests Routed to High-Latency Endpoints

**Severity:** P1 - Critical
**Status:** Open
**Created:** 2024-03-15 02:47 UTC
**Reported By:** NOC Automated Alerting
**Impacted Services:** routing, gateway, fulfillment
**Customer Impact:** 847 inference requests experiencing 10x expected latency

---

## Executive Summary

Production model-serving exchange is routing inference dispatch orders to the highest-latency endpoints instead of the lowest. This is causing cascading timeouts across the inference pipeline, with customer-facing SLA violations accumulating at approximately 12 per minute.

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 02:31 | PagerDuty alert: p99 latency for `/dispatch/inference` exceeds 4500ms threshold |
| 02:35 | On-call engineer confirms latency spike in Datadog APM |
| 02:38 | Initial hypothesis: Redis connection pool exhaustion - RULED OUT |
| 02:42 | Correlation found: latency spike coincides with route selection returning unexpected endpoints |
| 02:47 | Incident declared, escalated to platform team |

## Observed Behavior

When the routing service selects the optimal route for a dispatch order, it consistently returns the **worst** available endpoint rather than the best:

```
[2024-03-15T02:39:17.442Z] routing::select INFO
  order_id=dispatch-7a3f2c1e
  available_routes=[{channel:"inference-us-east-1", latency:12}, {channel:"inference-us-west-2", latency:847}, {channel:"inference-eu-central-1", latency:203}]
  selected_route={channel:"inference-us-west-2", latency:847}
  ANOMALY: Expected lowest latency route (inference-us-east-1, 12ms), got highest (inference-us-west-2, 847ms)
```

```
[2024-03-15T02:39:18.103Z] gateway::dispatch WARN
  order_id=dispatch-7a3f2c1e
  timeout_budget_ms=500
  actual_latency_ms=847
  status=SLA_VIOLATION
  msg="Inference dispatch exceeded SLA budget"
```

## Impacted Tests

The following test scenarios are failing in our nightly regression suite:

- `test_best_route_selection` - Expects route with minimum latency
- `test_routing_prefers_low_latency_endpoints` - Verifies latency-based selection
- `test_inference_dispatch_meets_sla` - End-to-end SLA compliance check
- `hyper_matrix_scenarios::routing_*` - Matrix tests for route optimization

## Metrics

| Metric | Expected | Observed |
|--------|----------|----------|
| Route selection latency preference | Minimum | Maximum |
| p99 inference latency | < 200ms | 4,847ms |
| SLA violations (last hour) | 0 | 847 |
| Failed dispatch orders | 0 | 312 |

## Diagnostic Queries

```sql
-- Orders routed to non-optimal endpoints (last 4 hours)
SELECT
    order_id,
    selected_route_latency,
    MIN(available_route_latency) as optimal_latency,
    selected_route_latency - MIN(available_route_latency) as latency_delta
FROM dispatch_routing_decisions
WHERE timestamp > NOW() - INTERVAL '4 hours'
GROUP BY order_id, selected_route_latency
HAVING selected_route_latency > MIN(available_route_latency)
ORDER BY latency_delta DESC
LIMIT 100;
```

## Business Impact

- **Customer Complaints:** 23 enterprise customers have reported degraded inference performance
- **Revenue at Risk:** ~$47,000/hour in inference compute charges during degraded state
- **SLA Credits:** Estimated $12,400 in credit obligations if not resolved within 2 hours

## Investigation Notes

The route selection logic in the routing module appears to be using an incorrect comparison when choosing the optimal route. Engineering should examine:

1. The comparator function used for route selection
2. Whether the selection prefers minimum vs maximum values
3. Route scoring calculation logic

## Related Alerts

- `routing_latency_anomaly_detected` - 02:31 UTC
- `sla_violation_rate_exceeded` - 02:35 UTC
- `inference_timeout_cascade` - 02:41 UTC

## Attachments

- [Datadog APM Trace](internal://traces/dispatch-7a3f2c1e)
- [Route Selection Decision Log](internal://logs/routing/2024-03-15)

---

**Next Update:** 2024-03-15 04:00 UTC or upon status change
