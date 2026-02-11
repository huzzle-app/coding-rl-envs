# Support Ticket #47291: Route Selection Algorithm Choosing High-Latency Channels

**Submitted by**: David Chen, Network Operations Lead
**Organization**: Metro Emergency Communications Authority
**Priority**: High
**Created**: 2024-03-20 11:34 UTC
**Product Area**: Routing / Channel Selection

---

## Problem Description

Our dispatch operators are reporting that the automatic route selection for inter-agency communications is consistently choosing higher-latency channels when lower-latency options are available and not blocked. This is causing noticeable delays in radio relay and data synchronization between our primary command center and field units.

We have three communication channels configured:
- **Alpha**: Satellite uplink, typically 45-80ms latency
- **Beta**: Microwave relay, typically 8-15ms latency
- **Gamma**: Fiber backhaul, typically 3-8ms latency

When all channels are healthy, we expect the system to prefer Gamma (lowest latency), then Beta, then Alpha. Instead, we're seeing Alpha selected even when Gamma shows 5ms latency.

---

## Steps to Reproduce

1. Navigate to Routing Configuration > Channel Status
2. Verify all three channels show "Available" status
3. Note the current latency readings (Alpha: 52ms, Beta: 12ms, Gamma: 5ms)
4. Send a test dispatch message
5. Check routing logs - message routed via Alpha

---

## Expected Behavior

Route selection should prefer the channel with the LOWEST latency among non-blocked candidates.

## Actual Behavior

Route selection appears to prefer the channel with the HIGHEST latency.

---

## Supporting Evidence

### Routing Decision Log

```
2024-03-20 11:28:14 [routing] Evaluating route candidates:
  - alpha: latency=52, blocked=false
  - beta: latency=12, blocked=false
  - gamma: latency=5, blocked=false
2024-03-20 11:28:14 [routing] Selected route: alpha (latency=52)
```

### Test Environment Validation

We ran the equivalent test in our staging environment:

```python
from ionveil.routing import choose_route

routes = [
    {"channel": "alpha", "latency": 52},
    {"channel": "beta", "latency": 12},
    {"channel": "gamma", "latency": 5},
]

selected = choose_route(routes, blocked=set())
print(selected)
# Output: {'channel': 'alpha', 'latency': 52}
# Expected: {'channel': 'gamma', 'latency': 5}
```

### Automated Test Failures

Our integration tests are catching this:

```
FAIL: tests/unit/routing_test.py::RoutingTests::test_choose_route_prefers_lowest_latency
AssertionError: Expected channel 'gamma', got 'alpha'
```

---

## Environment Details

- **IonVeil Version**: 2.4.1
- **Deployment**: On-premise (Metro EOC Primary)
- **Configuration**: 3 channels, no blocked routes
- **Traffic Volume**: ~2,400 messages/hour during incidents

---

## Business Impact

- **Latency Impact**: Messages taking 45-75ms longer than necessary
- **Capacity Waste**: Satellite channel has lower bandwidth, causing queuing
- **Cost**: Satellite time is metered at $0.12/MB vs included fiber
- **Reliability**: Alpha channel has 99.2% uptime vs Gamma's 99.97%

During our last major incident (apartment fire with evacuation), operators complained about sluggish radio relay. We traced it to 89% of traffic routing through Alpha despite Beta and Gamma being healthy.

---

## Workaround

We've temporarily blocked Alpha channel in configuration, forcing selection between Beta and Gamma. However:
1. This defeats the purpose of having redundant channels
2. Beta is now selected over Gamma (same bug pattern)
3. If we block both Alpha and Beta, we have no failover capacity

---

## Additional Context

The `choose_route()` function documentation says:
> "Returns the route with minimum latency among non-blocked candidates"

The sorting logic might be inverted. Looking at the code path:
- Candidates are filtered by blocked status
- Candidates with negative latency are excluded
- Remaining candidates are sorted
- First element of sorted list is returned

The sort key or sort order may be incorrect.

---

## Requested Resolution

Please investigate the route selection logic in `ionveil/routing.py` and correct the sorting behavior so lowest-latency channels are preferred.

---

## Contact Information

**Primary Contact**: David Chen, david.chen@metro-eca.gov, ext 4471
**Technical Contact**: Sarah Williams, sarah.williams@metro-eca.gov, ext 4485
**Escalation Path**: Metro EOC Director (for P1 incidents during active emergencies)
