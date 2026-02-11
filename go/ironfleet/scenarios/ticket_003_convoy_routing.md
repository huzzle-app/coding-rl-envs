# Support Ticket: FLEET-SUP-4821

**Priority:** High
**Status:** Escalated to Engineering
**Opened:** 2024-03-18 11:45 UTC
**Reporter:** MSG Rodriguez, 3rd Transportation Battalion
**Assignee:** Fleet Platform Team

---

## Subject

Convoy routing consistently selecting slowest available channels despite network conditions

---

## Description

Our convoys are consistently being routed through the highest-latency communication channels, even when lower-latency options are available and not blocked. This is causing significant delays in mission coordination and real-time telemetry updates.

Example from today's operations:

| Route Option | Latency (ms) | Status | Selected |
|--------------|--------------|--------|----------|
| SATCOM-Alpha | 450 | Available | YES |
| Mesh-Bravo | 85 | Available | No |
| Mesh-Charlie | 120 | Available | No |

The system chose SATCOM-Alpha (450ms) when Mesh-Bravo (85ms) was fully operational. This happened for 12 consecutive convoy dispatches this morning.

---

## Steps to Reproduce

1. Submit convoy mission with multiple available communication channels
2. Observe route selection in mission planning output
3. Note that highest-latency channel is consistently selected

---

## Expected Behavior

Routing should select the lowest-latency available channel that is not blocked or degraded.

---

## Actual Behavior

Routing selects the highest-latency channel from the available pool.

---

## Evidence

**Test Output** (from CI pipeline):
```
=== FAIL: TestChooseRouteIgnoresBlocked
    core_test.go:28: unexpected route: &{Channel:alpha Latency:8 Reliability:0 Blocked:false}
```

The test expected route "alpha" (latency=8) to be selected when "beta" (latency=2) was blocked, but the routing logic appears to be inverting the latency comparison.

**Stress Test Failures**:
```
=== FAIL: TestHyperMatrix/case_00005
    hyper_matrix_test.go:54: blocked route selected
=== FAIL: TestHyperMatrix/case_00010
    hyper_matrix_test.go:54: blocked route selected
```

**Fleet Telemetry Logs**:
```
2024-03-18T09:23:45Z INFO  route_selected convoy="ALPHA-7" channel="satcom-primary" latency=523
2024-03-18T09:23:45Z DEBUG available_channels=[{"channel":"mesh-1","latency":45},{"channel":"mesh-2","latency":78},{"channel":"satcom-primary","latency":523}]
```

---

## Routing Metrics

```
ironfleet_route_latency_selected_ms{p50} 387
ironfleet_route_latency_available_min_ms{p50} 62
ironfleet_routing_suboptimal_selection_total 847
```

The P50 selected latency is 6x higher than the minimum available latency.

---

## Business Impact

- Convoy coordination delays: +340ms average per message round-trip
- Mission telemetry staleness increased by factor of 5
- Bandwidth costs increased (SATCOM charges per-minute vs mesh is flat-rate)

---

## Workaround Attempted

Manually blocking high-latency channels forces selection of lower-latency options, but this is operationally impractical and risks losing backup channels.

---

## Related Issues

- FLEET-SUP-4756: Channel health scoring returns negative values (may be related)
- FLEET-SUP-4802: Route cost estimation seems too low

---

## Attachments

- routing_trace_20240318.log
- channel_metrics_snapshot.json
