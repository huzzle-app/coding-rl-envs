# Engineering Post-Mortem: Replay Subsystem State Corruption

**Incident ID:** POST-2024-0156
**Date of Incident:** 2024-11-12
**Duration:** 6 hours 23 minutes
**Author:** Platform Reliability Team
**Status:** Root Cause Under Investigation

---

## Incident Timeline

| Time (UTC) | Event |
|------------|-------|
| 02:14 | Kafka consumer lag alerts triggered in replay-processor fleet |
| 02:31 | First reports of state inconsistency from reconciliation jobs |
| 03:45 | Inflight counters showing negative values in dashboards |
| 04:12 | Circuit breakers stuck open despite healthy downstream services |
| 05:22 | Replay ordering confirmed broken - events processing out of sequence |
| 08:37 | Manual state reset completed, service restored |

## Symptoms Observed

### 1. Negative Inflight Counters

After replaying events, the `inflight` counter was going negative, which should be impossible:

```
Initial state: { inflight: 100, backlog: 50, version: 1000 }
After replay of 20 events with positive deltas: { inflight: -45, backlog: 250, ... }
```

The events had `inflightDelta: +5` but the counters were *decreasing* instead of increasing.

### 2. Events at Current Version Being Skipped

Events with `version` equal to `currentVersion` were being skipped during replay:

```
currentVersion: 1000
event.version: 1000  <- This should be applied but is being skipped
event.version: 1001  <- Only this one gets applied
```

We're losing the first applicable event on every replay.

### 3. Replay Ordering Reversed

The `orderedReplay` function is returning events in descending version order instead of ascending. This breaks causal ordering requirements:

```javascript
// Input: [{ version: 3 }, { version: 1 }, { version: 2 }]
// Expected output: [{ version: 1 }, { version: 2 }, { version: 3 }]
// Actual output: [{ version: 3 }, { version: 2 }, { version: 1 }]
```

### 4. Replay Budget Over-Allocation

The `replayBudget` function is allowing more events than intended. With a base rate of 12 and 100 queued events, we expected budget around 1200 but got ~1400.

Also, the function appears to be returning negative values in some edge cases??

### 5. Circuit Breaker Delays

The circuit breaker is taking 5 failures to open instead of the expected 4. During cascading failures, this extra request causes downstream saturation.

### 6. Retry Backoff Doubling

Retry delays are consistently ~2x higher than expected. First retry should be ~100ms but we're seeing ~200ms. The exponential backoff seems to start one power higher than intended.

## Affected Components

```
src/core/replay.js      - orderedReplay, replayBudget
src/core/resilience.js  - replayState, circuitOpen, retryBackoffMs
```

## Related Test Failures

```bash
npm test -- tests/unit/replay.test.js
npm test -- tests/unit/resilience.test.js
npm test -- tests/chaos/replay-storm.test.js
npm test -- tests/integration/replay-chaos.test.js
```

## Business Impact

- 847 transactions stuck in limbo during incident
- 12 duplicate shipments created due to failed idempotency
- $340K in expedited re-routing costs
- 3 carrier partners reported integration timeouts

## Questions for Investigation

1. Why is the `inflightDelta` being subtracted instead of added?
2. Why are events at the exact `currentVersion` being skipped?
3. Is the sort comparator in `orderedReplay` inverted?
4. What's the correct multiplier for `replayBudget`?
5. Should the circuit breaker open at 4 or 5 failures?

---

**Action Items:**
- [ ] Fix replay state delta application
- [ ] Fix version comparison boundary condition
- [ ] Fix replay ordering
- [ ] Verify circuit breaker threshold
- [ ] Add chaos test coverage for these edge cases

**Next Review:** 2024-11-15 10:00 UTC
