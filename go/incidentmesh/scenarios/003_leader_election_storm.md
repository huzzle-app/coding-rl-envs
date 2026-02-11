# Scenario 003: Leader Election Storm

## PagerDuty Alert Chain

---

### ALERT [CRITICAL] - 03:47:23 UTC

**Service**: incidentmesh-consensus
**Alert**: Leader election thrashing detected
**Cluster**: prod-east-1
**Duration**: 47 minutes and counting

```
Leader changes in last hour: 2,847
Expected: < 5
Node consensus failures: 100%
Split-brain conditions detected: 12
```

---

### ALERT [CRITICAL] - 03:48:01 UTC

**Service**: incidentmesh-dispatch
**Alert**: Dispatch service degraded - no stable leader

```
Dispatch requests failing: 100%
Error: "no leader available for region east-1"
Pending incidents: 89
```

---

### ALERT [WARNING] - 03:52:15 UTC

**Service**: incidentmesh-capacity
**Alert**: Capacity consensus lost

```
Hospital capacity data inconsistent across nodes
Node-1 reports: 847 beds available
Node-2 reports: 312 beds available
Node-3 reports: 1,203 beds available
```

---

## Slack Thread: #incident-response-platform

**@oncall-primary** (03:55 UTC):
We're seeing complete chaos in the consensus layer. Leader election is happening hundreds of times per minute. No node can hold leadership for more than a few seconds.

**@sre-lead** (03:57 UTC):
What are the symptoms exactly?

**@oncall-primary** (03:58 UTC):
1. Nodes are calling elections constantly
2. Even when a node gets elected, it immediately loses leadership
3. Vote counting seems broken - nodes with minority support are becoming leaders
4. Lease expiry is happening immediately even though we set 30-second leases

**@backend-eng** (04:02 UTC):
I looked at the logs. Some weird things:
- `SelectLeader` is always picking the first node in the list regardless of which node has the highest term
- When we check if a lease is expired, it says "expired" even though the lease was just renewed
- The quorum check returns false even when we have 3/5 nodes voting yes

**@oncall-primary** (04:05 UTC):
Also seeing that when a node steps down, it's NOT clearing its IsLeader flag. So we have multiple nodes thinking they're the leader simultaneously.

**@sre-lead** (04:07 UTC):
That would explain the split-brain. What about the term advancement?

**@backend-eng** (04:10 UTC):
`AdvanceTerm` is being called but the term number isn't actually incrementing. It's stuck at term 1 forever.

**@oncall-primary** (04:12 UTC):
More findings:
- `CountVotes` is counting ALL entries in the vote map as "yes" votes, even if the value is `false`
- `QuorumReached` needs 4/5 votes to pass (should be 3/5 for majority)
- `ResolveConflict` is picking the node with the LOWER term instead of higher

**@backend-eng** (04:15 UTC):
I checked `RenewLease` - it's setting the expiry time to `now` instead of `now + duration`. So every lease expires immediately.

**@oncall-secondary** (04:18 UTC):
The weighted election is also broken. `GetNodeWeight` returns 0 for all nodes regardless of their actual weight. The weighted quorum check uses total/3 threshold instead of total/2.

**@sre-lead** (04:22 UTC):
And `ElapsedSinceLease`?

**@oncall-secondary** (04:24 UTC):
It's using addition instead of subtraction. `now + leaseStart` instead of `now - leaseStart`. So elapsed time is always a huge number, triggering immediate expiry.

**@sre-lead** (04:27 UTC):
This is a nightmare. The entire consensus module is broken. Every function has some kind of logic error.

**@oncall-primary** (04:30 UTC):
Putting up a maintenance page for dispatch. We can't safely route incidents until consensus is fixed.

---

## Impact Summary

- **Dispatch Availability**: 0% for 2+ hours
- **Incidents Affected**: 89 pending, 12 failed over to backup system
- **Data Consistency**: Unknown - possible split-brain corruption
- **SLA Violation**: Yes, 99.99% uptime SLA breached

---

## Initial Triage Notes

The consensus/leader election system has multiple interacting bugs:
1. Leader selection ignores term numbers
2. Lease management sets wrong expiry times
3. Vote counting counts existence instead of value
4. Quorum thresholds are wrong
5. Term advancement doesn't actually advance
6. Leader stepdown doesn't clear flags
7. Conflict resolution picks wrong winner
8. Time calculations use wrong operators

All 14 functions in the consensus module may need review.

---

*Status: ONGOING - Engineering team investigating*
