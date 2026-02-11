# Support Ticket: STRATA-4521

**Priority**: High
**Status**: Escalated to Engineering
**Customer**: GlobalDefense Corp (Enterprise Tier)
**Created**: 2024-11-18 09:15 UTC
**Category**: Performance / Routing

---

## Customer Report

> "Our incident response teams are being routed through HIGH latency channels instead of optimal low-latency paths. We have multiple available routes but the system consistently picks the slowest one. This is adding 200-400ms to our response coordination."
>
> -- Maria Chen, SOC Director @ GlobalDefense Corp

## Ticket Details

**Environment**: Production (us-east-1)
**StrataGuard Version**: 2.4.1
**Account ID**: GDC-2847

## Issue Description

The `Routing.ChooseRoute()` function is selecting routes with the HIGHEST latency instead of the LOWEST. This behavior is the opposite of expected optimal routing.

### Customer Evidence

```
Route Options:
  alpha: 200ms latency
  beta:  50ms latency (blocked)
  gamma: 80ms latency

Expected Selection: gamma (80ms - lowest available)
Actual Selection: alpha (200ms - highest!)
```

### Internal Test Failures

```
FAILED: CoreTests.ChooseRouteIgnoresBlocked
  Route selected: alpha (latency=8)
  Expected: Route with lowest latency among non-blocked options

FAILED: HyperMatrixTests.HyperMatrixCase (route selection assertions)
  Multiple cases selecting suboptimal routes
```

## Technical Analysis

The route selection logic appears to use `OrderByDescending` when it should use `OrderBy`. This causes:

1. Highest latency routes selected first
2. Optimal paths bypassed
3. Response coordination delays

## Logs from Customer Environment

```
2024-11-18T08:47:22.001Z [INFO] routing.select: Evaluating routes
  candidates=[{channel:"alpha",latency:200},{channel:"gamma",latency:80}]
  blocked=["beta"]

2024-11-18T08:47:22.002Z [DEBUG] routing.select: Route chosen
  selected="alpha" latency=200
  note="First after OrderByDescending"  <-- Problem here

2024-11-18T08:47:22.445Z [WARN] dispatch.timing: Response delay detected
  expected_latency_ms=80 actual_latency_ms=200
  delta_ms=120 sla_impact="at_risk"
```

## Business Impact

- **SLA Risk**: 23 incidents this week with elevated response times
- **Customer Satisfaction**: GlobalDefense Corp threatening contract review
- **Operational Cost**: Additional bandwidth consumed on suboptimal routes

## Reproduction Steps

```csharp
var route = Routing.ChooseRoute(
    [new Route("alpha", 8), new Route("beta", 3)],
    new HashSet<string> { "beta" }
);

// Expected: null (only option is blocked) OR lowest available
// Actual: Returns "alpha" with latency 8 (highest)

// Another case:
var route2 = Routing.ChooseRoute(
    [new Route("fast", 10), new Route("slow", 100)],
    new HashSet<string>()
);
// Expected: "fast" (latency 10)
// Actual: "slow" (latency 100)
```

## Customer Workaround (Temporary)

Customer is manually overriding route selection in their integration layer, but this is unsustainable and adds operational complexity.

## Related Issues

- `RouteRank()` may have similar sorting issues
- `OptimalLeg()` for waypoints shows similar pattern

---

**Support Engineer**: James Wong
**Escalated To**: Platform Engineering
**Customer Contact**: maria.chen@globaldefense.com
**SLA Deadline**: 2024-11-19 09:15 UTC (24h response)
