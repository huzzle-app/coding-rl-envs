# ALERT: Failover Cascade - Circuit Breakers Triggering Prematurely

**Alert ID**: ALT-78234
**Severity**: CRITICAL
**Triggered**: 2024-03-22 03:47:12 UTC
**Source**: Prometheus/Alertmanager
**Runbook**: https://runbooks.internal/resilience/circuit-breaker-cascade

---

## Alert Details

```
FIRING: CircuitBreakerCascade

Cluster: prod-treasury-west
Affected Services: 12 of 16
Circuit Breaker State: OPEN (unexpected)

Error threshold reached at exactly configured limit.
Expected: Circuit opens ABOVE threshold
Actual: Circuit opens AT threshold

Duration: 2h 13m (ongoing)
```

---

## Metrics Snapshot

```
quorumledger_circuit_breaker_state{service="ledger"} = 1  # OPEN
quorumledger_circuit_breaker_state{service="settlement"} = 1  # OPEN
quorumledger_circuit_breaker_state{service="consensus"} = 1  # OPEN
quorumledger_circuit_breaker_errors{service="ledger"} = 10
quorumledger_circuit_breaker_threshold{service="ledger"} = 10

# Circuit opened at exactly 10 errors with threshold of 10
# Should only open when errors EXCEED threshold
```

---

## Related Alerts Firing

| Alert | Status | Since |
|-------|--------|-------|
| `LeaderElectionFailed` | FIRING | 03:47 UTC |
| `RetryBackoffExponentialGrowth` | FIRING | 03:52 UTC |
| `PartitionSeverityMisclassified` | FIRING | 03:55 UTC |
| `AvailabilityScoreNegative` | FIRING | 04:01 UTC |

---

## System Logs

```
2024-03-22T03:47:12Z ERROR resilience/failover: leader_election_failed
    candidates=["node-a","node-b","node-c"]
    degraded={"node-a":true}
    selected_leader=""
    error="no leader selected despite healthy candidates"

2024-03-22T03:47:15Z ERROR resilience/failover: circuit_breaker_opened
    service="ledger"
    error_count=10
    threshold=10
    note="opened at exact threshold, not above"

2024-03-22T03:47:18Z WARN  resilience/failover: retry_backoff_excessive
    attempt=1
    base_ms=100
    calculated_backoff=200
    expected_backoff=100
    note="attempt 1 should use base, not 2x base"

2024-03-22T03:48:01Z ERROR resilience/failover: availability_score_negative
    up_services=0
    total_services=4
    score=-1
    note="should be 0 for zero availability, not negative"

2024-03-22T03:48:22Z WARN  resilience/failover: partition_severity_wrong
    isolated_nodes=5
    total_nodes=10
    severity="critical"
    expected="major"
    note="50% exactly should be major, not critical"
```

---

## Failing Tests

```
--- FAIL: TestPickLeader
    resilience_test.go:11: unexpected leader: (empty string)

--- FAIL: TestCircuitBreakerState
    resilience_test.go:27: expected open at threshold

--- FAIL: TestRetryBackoff
    resilience_test.go:41: expected 200 for attempt 1, got 400

--- FAIL: TestPartitionSeverity
    resilience_test.go:51: expected critical for 50% partition
```

---

## Cascade Analysis

```
          [Initial Trigger]
                 |
                 v
    +----------------------------+
    | Leader election returns "" |
    | (empty string for leader)  |
    +----------------------------+
                 |
                 v
    +----------------------------+
    | Services cannot route to   |
    | leader, errors accumulate  |
    +----------------------------+
                 |
                 v
    +----------------------------+
    | Circuit breakers open at   |
    | exact threshold (too early)|
    +----------------------------+
                 |
                 v
    +----------------------------+
    | Retry backoff doubles one  |
    | extra time, causing delays |
    +----------------------------+
                 |
                 v
    +----------------------------+
    | Partition severity wrong,  |
    | escalation procedures fail |
    +----------------------------+
```

---

## Business Impact

- **Availability**: Effective cluster availability: 0%
- **Transactions**: 12,847 transactions queued, not processing
- **SLA Breach**: Exceeded 99.9% availability SLA at 04:15 UTC
- **On-Call**: All hands escalation triggered

---

## Immediate Actions Taken

1. Manual leader assignment attempted - failed (code ignores assignment)
2. Circuit breaker threshold raised to 15 - opened at 15 (same issue)
3. Rolled back to last known good config - no improvement
4. Engaged core engineering team

---

## Root Cause Hypothesis

Multiple bugs in the resilience/failover module:
- Leader election function returns empty string instead of valid candidate
- Circuit breaker opens at `>=` threshold instead of `>` threshold
- Retry backoff calculation starts loop at wrong index
- Partition severity boundary condition incorrect

---

## Recommended Investigation

Check `internal/resilience/failover.go` for:
1. Leader selection return value
2. Circuit breaker threshold comparison operator
3. Retry backoff loop starting index
4. Partition severity percentage boundaries
