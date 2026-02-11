# Incident Report INC-2024-0847

## Classification
- **Priority**: P1 - Critical
- **Status**: Open
- **Service**: NebulaChain Supply Provenance Platform
- **Component**: Routing Engine
- **Reported By**: Global Operations Center (GOC)
- **Date**: 2024-11-15T08:42:00Z

## Executive Summary

Multiple high-priority shipments are experiencing significant delays due to the routing engine consistently selecting suboptimal channels. Vessel traffic is being directed through the highest-latency routes despite lower-latency alternatives being available and operational.

## Impact

- **Financial**: Estimated $2.4M in delay penalties across 47 shipments in the last 12 hours
- **SLA Breaches**: 23 Priority-1 dispatch tickets now exceeding contractual delivery windows
- **Customer Escalations**: 8 Tier-1 logistics partners have opened severity-critical cases
- **Operational**: Rotterdam and Singapore terminals reporting berth congestion as vessels arrive clustered instead of staggered

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 06:15 | NOC notices elevated average transit times on APAC-EMEA corridor |
| 06:28 | First customer complaint: container vessel MV Horizon Star routed via Cape route instead of Suez |
| 06:45 | Automated latency monitoring triggers warning threshold |
| 07:02 | Second vessel MV Pacific Grace takes northern route despite 3x latency vs. alternative |
| 07:30 | GOC initiates P2 incident, begins investigation |
| 08:15 | Pattern confirmed: routing consistently picks worst-latency channels |
| 08:42 | Escalated to P1, development team engaged |

## Observed Behavior

When the routing engine evaluates candidate channels, it appears to prefer channels with higher latency. Log analysis shows:

```
[2024-11-15T06:28:14.332Z] INFO routing: chooseRoute candidates=[
  { channel: "suez-express", latency: 4.2 },
  { channel: "cape-standard", latency: 18.7 },
  { channel: "atlantic-north", latency: 12.1 }
]
[2024-11-15T06:28:14.334Z] INFO routing: selected={ channel: "cape-standard", latency: 18.7 }

[2024-11-15T07:02:41.891Z] INFO routing: chooseRoute candidates=[
  { channel: "arctic-direct", latency: 22.3 },
  { channel: "baltic-feeder", latency: 8.1 },
  { channel: "channel-tunnel", latency: 6.9 }
]
[2024-11-15T07:02:41.892Z] INFO routing: selected={ channel: "arctic-direct", latency: 22.3 }
```

The routing engine is selecting the channel with the worst (highest) latency instead of the best (lowest).

## Affected Tests

The following tests are failing in the current test suite:

- `chooseRoute ignores blocked channels` (unit/routing.test.js) - intermittent failures when multiple candidates present
- `hyper-matrix-00038` through `hyper-matrix-00142` - route selection assertions failing
- `hyper-matrix-02891`, `hyper-matrix-03456`, `hyper-matrix-05102` - latency ordering violations
- `service-mesh-matrix` routing scenarios - downstream cascading failures

## Investigation Notes

1. The `chooseRoute` function in `src/core/routing.js` handles channel selection
2. Sort order appears inverted - the comparison function may be sorting in the wrong direction
3. Similar issue may exist in `services/routing/service.js` for weighted route scoring
4. Tiebreaking by channel name appears to work correctly when latencies are equal

## Workaround

None currently available. Manual route override is not supported in the current dispatch flow.

## Attachments

- routing_decision_audit_20241115.json (12,847 routing decisions showing pattern)
- latency_histogram_last_24h.png
- customer_escalation_tickets.csv

---
**Incident Commander**: Sarah Chen, Senior SRE
**Next Update**: 2024-11-15T10:00:00Z
