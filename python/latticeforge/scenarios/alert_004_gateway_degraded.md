# Production Alert: Gateway Selecting Degraded Nodes

**Alert ID:** ALT-GW-2024-1847
**Source:** Prometheus/Alertmanager
**Severity:** Warning
**Fired:** 2024-03-22 16:45:32 UTC

## Alert Details

```
ALERT: GatewayDegradedNodeSelection
Status: FIRING
Severity: warning
Service: gateway
Instance: gateway-prod-01

Summary: Gateway consistently routing traffic to degraded nodes
Description: Over 80% of requests in the last 15 minutes were routed
             to nodes with degraded=true or high saturation scores.

Labels:
  - service: gateway
  - environment: production
  - team: platform

Annotations:
  - runbook: https://wiki.internal/runbooks/gateway-routing
  - dashboard: https://grafana.internal/d/gateway-health
```

## Metrics Snapshot

```
# Routing decisions (last 15 min)
gateway_route_selections_total{node_status="degraded"} 847
gateway_route_selections_total{node_status="healthy"} 112

# Node scores at selection time
gateway_selected_node_score_avg 623.4
gateway_available_node_score_min 45.2

# Latency impact
gateway_request_latency_p99{quantile="0.99"} 1247ms
gateway_request_latency_p99{quantile="0.50"} 892ms
```

## Context

The gateway service selects primary nodes for request routing based on a scoring function. Lower scores indicate healthier nodes:
- Base latency in ms
- Queue depth * 3.4
- Saturation * 120
- Degraded penalty: +500

Despite healthy nodes being available with scores ~45, the gateway is selecting nodes with scores >600.

## Suspected Issue

The node selection function may be using `max()` instead of `min()` when choosing the best candidate.

## Related Code

```python
# gateway/service.py - select_primary_node()
# Should select lowest score (healthiest), but appears to select highest
```

## Impacted Tests

- `test_select_primary_prefers_lowest_score`
- `test_gateway_avoids_degraded_nodes`
- `test_route_chain_healthy_path`

## Escalation Path

1. Platform team (primary)
2. SRE on-call (if p99 latency > 2000ms)
3. Incident commander (if customer-facing impact confirmed)
