# INCIDENT-002: Consensus Failures During Peak Trading Hours

**Severity**: P1 - Critical
**Status**: Investigating
**Reported By**: Platform Reliability
**Date**: 2024-03-18 14:23 UTC
**Affected Systems**: Consensus Engine, Quorum Validation

---

## Executive Summary

The distributed consensus layer is failing to reach quorum on valid voting rounds. Transactions that should achieve consensus are being rejected, causing settlement delays. Byzantine fault tolerance calculations also appear incorrect, leaving the system vulnerable during node failures.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 2024-03-18 13:45 | First transaction timeout reported |
| 2024-03-18 13:52 | SRE notices spike in consensus rejections |
| 2024-03-18 14:10 | Multiple settlement batches stuck in pending |
| 2024-03-18 14:23 | Incident declared after 47 failed consensus rounds |

---

## Symptoms Observed

### 1. Quorum check fails at exact threshold
Votes achieving exactly 66% approval are being rejected:

```
2024-03-18T14:15:22Z ERROR consensus/quorum: quorum_check_failed
    votes=6 approved=4 ratio=0.6667 threshold=0.66
    result="rejected"
    expected="approved"
```

### 2. Byzantine tolerance calculation wrong
With 7 nodes, system reports tolerance of 1 (should be 2):

```
2024-03-18T14:17:33Z WARN  consensus/quorum: byzantine_tolerance
    total_nodes=7 calculated_tolerance=1
    note="3f+1 formula suggests tolerance should be 2"
```

### 3. Approval ratio returning invalid values
Some calls return ratio > 1.0:

```
--- FAIL: TestApprovalRatio
    quorum_test.go:14: unexpected ratio: 1.5000
```

### 4. Quorum health status inverted
Strong consensus (90%+) being classified as "adequate", while weak consensus (66%) classified as "strong":

```
2024-03-18T14:19:44Z INFO  consensus/quorum: health_check
    approval_ratio=0.92 health="adequate"
    note="should be 'strong' at 92%"
```

---

## Failing Test Scenarios

```
--- FAIL: TestHasQuorum
    quorum_test.go:22: expected quorum

--- FAIL: TestByzantineTolerance
    quorum_test.go:35: expected tolerance 2 for 7 nodes

--- FAIL: TestIsSupermajority
    quorum_test.go:44: expected supermajority for 2/3

--- FAIL: TestQuorumHealth
    quorum_test.go:51: expected weak for 1/2 ratio, got strong

--- FAIL: TestNetworkPartitionQuorum
    network_partition_test.go:13: expected quorum under partial partition
```

---

## Business Impact

- **Throughput**: 340 transactions blocked awaiting consensus
- **Latency**: Average consensus time increased from 45ms to timeout (30s)
- **Availability**: Effective system availability dropped to 23%
- **Risk**: Byzantine tolerance miscalculation could allow split-brain

---

## Network Topology During Incident

```
Cluster: prod-consensus-east
Nodes: 7 (all healthy, no partitions)

Node      | Vote  | Expected | Actual
----------|-------|----------|--------
node-01   | YES   | Counted  | Counted
node-02   | YES   | Counted  | Counted
node-03   | NO    | Counted  | Counted
node-04   | YES   | Counted  | Counted
node-05   | YES   | Counted  | Counted
node-06   | NO    | Counted  | Counted
node-07   | YES   | Counted  | Counted

Approval: 5/7 = 71.4% > 66% threshold
Expected: QUORUM ACHIEVED
Actual: QUORUM REJECTED
```

---

## Suspected Areas

- Threshold comparison logic (off-by-one or wrong operator)
- Byzantine tolerance formula implementation
- Quorum health classification thresholds
- Ratio calculation returning hardcoded/invalid values

---

## Action Required

Fix consensus validation logic. Trading suspended on affected pairs until resolution. Maximum acceptable resolution time: 2 hours.
