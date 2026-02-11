# Scenario 5: Distributed Consensus and State Management Failures

## Post-Mortem Document

**Incident Title**: Multi-Region State Corruption and Split-Brain Event
**Date**: 2024-01-18
**Duration**: 4 hours 23 minutes
**Severity**: P1 - Critical
**Author**: SRE Team

---

## Executive Summary

A network partition between our us-east-1 and us-west-2 regions led to a split-brain scenario where two nodes both believed they were the leader. This resulted in conflicting state mutations, corrupted infrastructure state snapshots, and lost customer updates. Multiple distributed systems bugs contributed to both the initial failure and the extended recovery time.

---

## Timeline of Events

**14:32 UTC** - Network connectivity degraded between regions
**14:33 UTC** - Both us-east-1-leader and us-west-2-leader simultaneously claimed leadership
**14:35 UTC** - Conflicting state mutations detected in infrastructure state store
**14:38 UTC** - Distributed locks being stolen prematurely (TTL of 5s too short)
**14:42 UTC** - Quorum checks passing incorrectly with only 2 of 5 nodes (should need 3)
**14:45 UTC** - Version vector merge losing updates (using min instead of max)
**14:48 UTC** - State snapshot attempted during active writes, resulting in corruption
**15:23 UTC** - Operations attempted concurrent resource updates; lost-update problem observed
**16:15 UTC** - Dependency graph cycle detected in recovery, blocking reconciliation
**18:55 UTC** - Full service restored after manual intervention

---

## Root Cause Analysis

### 1. Leader Election Race Condition

Two candidates simultaneously saw `leader_id = None` and both set themselves as leader. The campaign function is not using atomic compare-and-swap:

```python
# Observed behavior
if self.leader_id is None:       # Both candidates see None
    self.leader_id = candidate_id  # Both set themselves
    self.is_leader = True
```

There's also no fencing token mechanism to prevent stale leaders from making mutations.

### 2. Distributed Lock TTL Too Short

Operations that take 10-30 seconds were protected by locks with only a 5-second TTL. This allowed locks to be "stolen" mid-operation:

```
Operation start: Lock acquired (TTL=5s)
Operation at 6s: Lock expired, stolen by another worker
Operation at 8s: Original worker writes assuming it has lock
Result: Conflicting writes
```

### 3. Quorum Off-By-One

The quorum checker allowed operations with exactly half the nodes (2 of 5), when it should require a strict majority (3 of 5):

```python
# Current (broken)
return responding_nodes >= self.total_nodes / 2  # 2.5 -> allows 2

# Should be
return responding_nodes > self.total_nodes / 2   # Requires 3
```

### 4. Version Vector Merge Using Min Instead of Max

When merging version vectors from divergent replicas, the code used `min()` instead of `max()`, causing acknowledged writes to be lost:

```python
# Broken merge - loses updates
merged.versions[node] = min(v1, v2)

# Correct merge - preserves all updates
merged.versions[node] = max(v1, v2)
```

### 5. State Transition Race Condition

The state machine allows concurrent transitions without locking. Two threads both saw a resource in ACTIVE state and transitioned it to UPDATING and DELETING simultaneously:

```
Thread A: Read state=ACTIVE, transition to UPDATING
Thread B: Read state=ACTIVE, transition to DELETING (race!)
Result: State corrupted, resource in undefined state
```

### 6. Lost Updates Due to Missing Optimistic Concurrency

The `update_resource` method accepts an `expected_version` parameter but completely ignores it:

```python
def update_resource(self, resource_id, config, expected_version=None):
    # expected_version is ignored - no version check!
    resource.desired_config = config
    resource.version += 1
```

This allows concurrent updates to overwrite each other (last writer wins).

### 7. Eventual Consistency Reads Without Staleness Flag

`get_resource()` returns resources directly without any indication of whether the state has converged. Clients read resources during consistency windows and make decisions on stale data.

### 8. Drift Detection Using Naive Dict Comparison

The `detect_drift()` function compares desired vs actual config using `!=` which fails for:
- Floating-point values (0.1 + 0.2 != 0.3)
- Lists with same elements in different order
- None vs missing keys

### 9. No Cycle Detection in Dependency Graph

The dependency graph builder doesn't detect cycles. When a circular dependency was introduced (A->B->C->A), the reconciliation loop ran indefinitely.

### 10. State Snapshot Corruption

Snapshots are taken without holding any locks. Concurrent writes during snapshot capture resulted in partial/inconsistent state being serialized.

---

## Observed Symptoms

### Monitoring Alerts

```
[CRITICAL] SplitBrainDetected
  Leaders: [us-east-1-node-03, us-west-2-node-01]
  Expected: 1 leader

[CRITICAL] QuorumViolation
  Operation: state_update
  Responding nodes: 2
  Required: 3 (majority of 5)

[WARNING] LockStolenDuringOperation
  Lock: resource-update-lock
  Original TTL: 5 seconds
  Operation duration: 12 seconds

[CRITICAL] StateSnapshotCorruption
  Snapshot ID: snap-2024-01-18-1448
  Resources captured: 847
  Resources expected: 1203

[WARNING] VersionVectorRegression
  Node: us-west-2
  Before merge: {us-east-1: 45, us-west-2: 32}
  After merge: {us-east-1: 42, us-west-2: 30}  # DECREASED!
```

### Customer Impact

```
Ticket #8923: "My resource shows 'creating' status for 2 hours"
  - Resource stuck due to concurrent state transition

Ticket #8924: "Configuration changes not being applied"
  - Lost update due to optimistic concurrency failure

Ticket #8931: "Infrastructure drifted but no alerts"
  - Drift detection missed due to float comparison issues
```

---

## Affected Components

- `shared/infra/state.py` - State machine, drift detection, snapshots
- `shared/infra/reconciler.py` - Reconciliation loop, dependency graph
- `shared/utils/distributed.py` - Leader election, distributed locks, quorum, version vectors

---

## Test Failures Related

```
FAILED tests/unit/test_infrastructure_state.py::TestStateManager::test_state_transition_locking
FAILED tests/unit/test_infrastructure_state.py::TestStateManager::test_optimistic_concurrency
FAILED tests/unit/test_infrastructure_state.py::TestStateManager::test_drift_detection_floats
FAILED tests/unit/test_infrastructure_state.py::TestStateManager::test_dependency_cycle_detection
FAILED tests/unit/test_infrastructure_state.py::TestStateManager::test_snapshot_consistency

FAILED tests/integration/test_service_communication.py::TestDistributed::test_leader_election_single_leader
FAILED tests/integration/test_service_communication.py::TestDistributed::test_lock_ttl_sufficient
FAILED tests/integration/test_service_communication.py::TestDistributed::test_quorum_requires_majority
FAILED tests/integration/test_service_communication.py::TestDistributed::test_version_vector_merge_max
FAILED tests/integration/test_service_communication.py::TestDistributed::test_lock_ordering_prevents_deadlock

FAILED tests/chaos/test_partition_tolerance.py::test_split_brain_prevention
FAILED tests/chaos/test_partition_tolerance.py::test_quorum_during_partition
```

---

## Impact Assessment

| Category | Impact |
|----------|--------|
| Customer data loss | 23 configuration updates lost |
| Service availability | 4h 23m degraded state |
| Infrastructure orphans | 156 resources in undefined state |
| Recovery effort | 18 engineer-hours |
| Customer credits issued | $12,500 |

---

## Lessons Learned

1. Distributed locks need TTLs longer than the longest expected operation
2. Leader election requires fencing tokens, not just presence checks
3. Quorum must be a strict majority, not "half or more"
4. Version vectors must use max() for merge, never min()
5. State machines need locking around transitions
6. Optimistic concurrency control must actually check versions
7. Snapshots need to be isolated from concurrent writes
8. Dependency graphs must be validated for cycles before use
