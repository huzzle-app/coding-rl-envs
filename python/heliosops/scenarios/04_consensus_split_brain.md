# INCIDENT-2024-1902: Cluster Consensus Failures During Node Scaling

**Severity**: CRITICAL
**Status**: MITIGATED (Root Cause Pending)
**Detected**: 2024-03-20 22:47 UTC
**Duration**: 2 hours 14 minutes
**Affected Service**: heliosops-policy, heliosops-resilience

---

## Executive Summary

During a planned scale-up of the HeliosOps cluster from 4 to 6 nodes, the consensus mechanism began accepting configuration changes without a true majority. This resulted in two conflicting operational policies being active simultaneously -- one partition running in "restricted" mode while another operated in "normal" mode, causing inconsistent dispatch behavior across regions.

## Impact

- 312 incidents dispatched under conflicting policies
- 28 SLA breaches due to restricted-mode throttling applied inconsistently
- Manual intervention required to reconcile cluster state
- 2+ hours of degraded operations

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 22:30 | Planned maintenance: adding nodes 5 and 6 to cluster |
| 22:35 | Nodes 5 and 6 join, begin synchronization |
| 22:41 | Network partition detected between nodes (1,2,3) and (4,5,6) |
| 22:47 | ALERT: Policy state inconsistency detected |
| 22:48 | Partition 1 (nodes 1,2,3): Votes to escalate to "restricted" mode |
| 22:49 | Partition 2 (nodes 4,5,6): Maintains "normal" mode |
| 22:51 | Both partitions report "consensus reached" -- this should be impossible |
| 23:15 | SRE identifies split-brain condition |
| 23:45 | Network partition resolved |
| 00:02 | Manual policy reconciliation completed |
| 01:01 | Cluster fully operational |

## Technical Analysis

### Consensus Check Behavior

The consensus system requires a **strict majority** (more than half of nodes) to agree before a decision is accepted. With 6 nodes, this means 4+ must agree.

However, during the incident, we observed:
- Partition 1 (3 nodes): Consensus check returned TRUE
- Partition 2 (3 nodes): Consensus check returned TRUE

With 6 total nodes, neither partition of 3 should have been able to reach consensus.

### Vote Distribution

```
Node 1: VOTE_YES (restricted mode)
Node 2: VOTE_YES (restricted mode)
Node 3: VOTE_YES (restricted mode)
------- network partition -------
Node 4: VOTE_NO (normal mode)
Node 5: VOTE_NO (normal mode)
Node 6: VOTE_NO (normal mode)
```

Both sides had exactly 50% of votes (3 out of 6). Neither should have achieved consensus.

### Observed Consensus Results

```python
# Partition 1
check_consensus(votes={"1": True, "2": True, "3": True},
                nodes=["1", "2", "3"])
# Returned: True (3 >= 3/2 = 1.5)

# Partition 2
check_consensus(votes={"4": False, "5": False, "6": False},
                nodes=["4", "5", "6"])
# Returned: True (0 >= 0/2 = 0)  # Wait, this was checking the wrong thing
```

Actually, looking at this more carefully -- each partition was only checking consensus among the nodes it could see, not the full cluster. That's a separate issue.

But even when checking full cluster consensus, the condition seems wrong:

```python
# Full cluster check that should have failed
check_consensus(votes={"1": True, "2": True, "3": True},
                nodes=["1", "2", "3", "4", "5", "6"])
# Returned: True (3 >= 6/2 = 3.0)
```

**3 >= 3 is true, but 3 is not a strict majority of 6**

### Leader Election Anomaly

Additionally, during failover testing, we noticed non-deterministic leader election when two nodes registered at the exact same timestamp. The election would sometimes pick one, sometimes the other, depending on dict iteration order.

## Questions for Investigation

1. Is the consensus check using `>=` when it should use `>`?
2. What constitutes a "strict majority" -- is `n/2 + 1` the correct threshold?
3. Why does leader election behave non-deterministically with identical timestamps?
4. Should the `LeaderElection.elect_leader()` use `<` instead of `<=` for comparison?

## Affected Code Paths

Based on logs and behavior:
- `heliosops/policy.py` - `check_consensus()` function
- `heliosops/resilience.py` - `LeaderElection.elect_leader()` method

## Mitigation Applied

1. Increased quorum threshold manually in config
2. Disabled automatic policy escalation
3. Forced cluster into single-primary mode
4. Scheduled investigation for permanent fix

## Action Items

- [ ] Review consensus threshold calculation in `policy.py`
- [ ] Audit leader election tie-breaking logic in `resilience.py`
- [ ] Add chaos testing for network partition scenarios
- [ ] Implement cluster-aware node list for partition detection

---

**Incident Commander**: @sre-lead-morgan
**Participants**: Platform team, Dispatch team, SecOps
**Post-Incident Review**: Scheduled for 2024-03-22
