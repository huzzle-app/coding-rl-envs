# ALERT-ROUTING-2024-1892: Route Scoring and Cost Calculation Anomalies

## Alert Details

**Alert ID**: ROUTING-COST-DRIFT-1892
**Triggered**: 2024-11-12 14:23 UTC
**Severity**: P2 - High
**Component**: ChronoMesh Routing Engine
**Dashboard**: https://chronomesh-internal.port/grafana/d/routing-metrics

---

## Anomaly Detection Summary

Our ML-based cost anomaly detector flagged significant deviations in two routing subsystems over the past 72 hours:

### Metric 1: Channel Score Distribution Shift

The `channel_score()` function is producing scores that don't match historical patterns:

```
Historical baseline (Oct 2024):
  - Mean channel score: 42.3
  - Std deviation: 8.7
  - Score range: [15, 89]

Current observed (Nov 12-14):
  - Mean channel score: 127.4  (+201% deviation)
  - Std deviation: 34.2
  - Score range: [45, 312]
```

**Analysis Notes:**
- Scores should decrease as reliability increases (inverse relationship)
- Current behavior shows scores increasing with reliability
- Formula appears to be additive where it should be divisive
- High-reliability channels (0.95+) now have worse scores than low-reliability (0.60)

**Sample calculation discrepancy:**
```
Input: latency=50ms, reliability=0.95, priority=8
Expected score: 50 / 0.95 * (10-8) = 105.26
Actual score: 50 + 0.95 * (10-8) = 51.9

Wait, that's lower... let me recalculate with real data:
Input: latency=50ms, reliability=0.80, priority=3
Expected: 50 / 0.80 * 7 = 437.5
Actual: 50 + 0.80 * 7 = 55.6

The scoring is completely wrong - it should penalize low reliability heavily.
```

### Metric 2: Route Cost Estimates Below Expected Floor

The `estimate_route_cost()` function is returning values lower than the fuel-cost floor:

```
Fuel rate: $2.50/km
Distance: 1000km
Latency: 200ms
Delay surcharge rate: $0.50/ms

Expected cost: (2.50 * 1000) + (200 * 0.50) = $2,600
Actual cost: (2.50 * 1000) - (200 * 0.50) = $2,400

Cost is $200 BELOW fuel-only baseline!
```

**Business Impact:**
- Route optimization is selecting wrong channels
- Invoices are underbilling customers by estimated $47,000/week
- Fuel cost recovery falling short of actuals

---

## Service Discovery Issue

Additionally, the contracts team reported that service URL resolution is broken:

```
Request: get_service_url("gateway", "api.chronomesh.io")
Expected: "http://api.chronomesh.io:8140"
Actual: "http://api.chronomesh.io"

The port number is missing from generated URLs!
```

This is causing 502 errors when services attempt to connect using the returned URLs, as they hit port 80 instead of the actual service ports.

**Affected services:**
- gateway (should be :8140)
- routing (should be :8141)
- policy (should be :8142)
- All 8 services in SERVICE_DEFS

---

## Rollback Consideration

The routing module was last deployed 2024-11-08. No code changes were made since then, but this may be a latent bug that's now causing visible impact due to increased traffic volume.

---

## Investigation Checklist

- [ ] Verify `channel_score()` formula - is reliability being used correctly?
- [ ] Check arithmetic operators in `estimate_route_cost()`
- [ ] Confirm `get_service_url()` includes port in URL construction
- [ ] Run routing test suite to reproduce failures
- [ ] Compare production metrics with test suite assertions

---

## Related Files

- `src/routing.cpp`: `channel_score()`, `estimate_route_cost()`
- `src/contracts.cpp`: `get_service_url()`
- Test files covering route scoring and cost estimation
