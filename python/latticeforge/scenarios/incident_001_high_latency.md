# Incident Report: Unexplained High Latency to Ground Stations

**Incident ID:** INC-2024-0847
**Reported by:** Network Operations Center
**Severity:** P2 - High
**Status:** Open
**Created:** 2024-03-15 14:32 UTC

## Summary

Ground station communications are consistently routed through high-latency paths despite multiple low-latency stations being available and healthy.

## Symptoms

- Average command latency increased from ~45ms to ~890ms over the past 48 hours
- No network degradation detected on any ground station
- All stations report "healthy" status in monitoring dashboards
- Latency spikes correlate with orbital passes over regions with multiple station options

## Impact

- Mission-critical commands are delayed, affecting orbital maneuver windows
- Telemetry lag causing stale data in flight director console
- Near-miss on collision avoidance maneuver due to command delay

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 03-13 08:00 | Normal operations, avg latency 42ms |
| 03-13 22:15 | Deployment of routing module update |
| 03-14 06:00 | First latency alerts triggered |
| 03-15 14:32 | Incident opened after flight director escalation |

## Investigation Notes

1. Checked network connectivity - all stations reachable with expected RTT
2. Verified station capacity - no congestion or queue buildup
3. Examined routing logs - system consistently selects stations with highest latency values
4. Blackout list is empty, no stations excluded

## Relevant Logs

```
2024-03-15 14:28:11 INFO  routing: evaluating stations=['goldstone', 'canberra', 'madrid']
2024-03-15 14:28:11 DEBUG routing: latencies={'goldstone': 45, 'canberra': 890, 'madrid': 62}
2024-03-15 14:28:11 INFO  routing: selected station='canberra'
```

## Failing Tests

- `test_select_primary_prefers_lowest_score`
- `test_plan_avoids_degraded_failover_region`
- Multiple gateway routing tests

## Questions for Engineering

1. Was there a change to the station selection algorithm recently?
2. Are we using min or max for latency optimization?
3. Could this be related to the routing module update on 03-13?
