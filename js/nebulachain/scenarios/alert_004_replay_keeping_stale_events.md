# ALERT: Event Replay Deduplication Failure

## Alert Details
- **Alert ID**: ALT-2024-4729
- **Severity**: Warning
- **Source**: Resilience Monitoring Dashboard
- **Triggered**: 2024-11-21T03:47:22Z
- **Service**: NebulaChain Event Replay System

---

## Alert Summary

```
ALERT TRIGGERED: replay_sequence_anomaly
Threshold exceeded: duplicate events per replay window > 0
Current value: 847 duplicate events in last hour
Expected: 0 (deduplication should eliminate duplicates)
```

## Metrics Snapshot

```
┌─────────────────────────────────────────────────────────────┐
│ REPLAY HEALTH DASHBOARD - Last 60 Minutes                  │
├─────────────────────────────────────────────────────────────┤
│ Total events processed:        12,847                       │
│ Unique events expected:         8,234                       │
│ Unique events actual:           7,387                       │
│ Stale/duplicate retained:         847                       │
│                                                             │
│ Sequence ordering issues:          23                       │
│ Checkpoint timing errors:          41                       │
│ Circuit breaker false opens:       12                       │
├─────────────────────────────────────────────────────────────┤
│ STATUS: DEGRADED                                            │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Observations

### 1. Stale Sequence Retention

The replay deduplication function is keeping events with the **lowest** sequence number instead of the **latest** (highest):

```
[03:42:18.114Z] DEBUG resilience: dedup input events=[
  { id: "evt-001", sequence: 15, type: "dispatch" },
  { id: "evt-001", sequence: 23, type: "dispatch" },
  { id: "evt-001", sequence: 19, type: "dispatch" }
]
[03:42:18.115Z] DEBUG resilience: dedup result kept={ id: "evt-001", sequence: 15 }
# ERROR: Should have kept sequence 23 (latest), not 15 (oldest)
```

This causes downstream systems to process stale event data, leading to:
- Incorrect dispatch status updates
- Provenance chain gaps
- Audit trail inconsistencies

### 2. Checkpoint Triggering Too Early

The checkpoint mechanism is triggering when sequence difference equals the interval instead of exceeds it:

```
[03:44:02.991Z] INFO resilience: checkpoint_check current=1050 last=1000 interval=50
[03:44:02.992Z] INFO resilience: checkpoint triggered (diff >= interval)
# Expected: Should only trigger when diff > interval (i.e., at 1051)
```

This creates excessive checkpoint overhead and storage costs.

### 3. Circuit Breaker Opening Prematurely

The circuit breaker is tripping when failures **equal** the threshold instead of **exceed** it:

```
[03:45:11.234Z] WARN resilience: circuit_breaker failures=5 threshold=5
[03:45:11.235Z] WARN resilience: state transition CLOSED -> OPEN
# Expected: Should remain CLOSED until failures > 5
```

Premature circuit breaking causes unnecessary service interruptions.

### 4. Half-Open State Not Rate-Limited

When circuit breaker enters HALF_OPEN state, it allows all traffic through instead of limiting probe requests:

```
[03:48:22.001Z] INFO resilience: circuit_breaker state=HALF_OPEN
[03:48:22.002Z] INFO resilience: allowRequest result=true (count: 1)
[03:48:22.003Z] INFO resilience: allowRequest result=true (count: 2)
[03:48:22.004Z] INFO resilience: allowRequest result=true (count: 3)
... (50 more requests all allowed)
```

## Affected Test Suites

- `resilience.test.js` - replay and circuit breaker unit tests
- `hyper-matrix-01000` through `hyper-matrix-01500` - deduplication scenarios
- `hyper-matrix-03000` through `hyper-matrix-03200` - sequence ordering tests
- `replay-chaos.test.js` - integration tests for replay under failure
- `service-mesh-matrix` resilience scenarios

## Runbook Actions

1. **Immediate**: Monitor replay lag; if exceeds 5 minutes, trigger manual replay catchup
2. **Investigation**: Review `src/core/resilience.js` for sequence comparison logic
3. **Review**: Check `replay()` function's deduplication key and comparison operators
4. **Verify**: Confirm checkpoint interval boundary conditions

## Escalation

Auto-escalating to on-call SRE if:
- Duplicate event rate exceeds 10% for 30 minutes
- Checkpoint storage growth exceeds 2GB/hour
- Circuit breaker flip rate exceeds 10/minute

---

**On-Call Engineer**: Alex Thompson
**Runbook**: https://runbooks.nebulachain.internal/resilience-replay-001
