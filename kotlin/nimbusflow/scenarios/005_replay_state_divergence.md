# Post-Incident Review: Event Replay State Divergence

**Incident:** NMB-PIR-2024-0203
**Date of Incident:** 2024-09-08
**Duration:** 6h 45m
**Severity:** P2 - Major
**Author:** Platform Resilience Team

---

## Incident Summary

Following a scheduled failover to the disaster recovery site, the event replay mechanism produced divergent state compared to the primary datacenter. Vessels that had been processed showed as pending, and duplicate dispatch orders were issued.

## Background

NimbusFlow uses event sourcing for dispatch state. When a region fails over, the replay mechanism processes the event log to reconstruct current state. Events are keyed by ID and have monotonically increasing sequence numbers. For duplicate events (same ID, different sequences), the system should keep the LATEST (highest sequence) event.

## What Happened

### 08:00 UTC - Planned Failover Initiated
- Primary datacenter taken offline for maintenance
- DR site activated, event replay triggered
- 847,000 events replayed in 12 minutes

### 08:15 UTC - Anomalies Detected
- Monitoring shows 2,341 vessels in "pending" state that should be "departed"
- Dispatch queue contains orders that were already fulfilled
- Duplicate berth allocation requests issued

### 08:45 UTC - Root Cause Hypothesis
- Event replay is not keeping the latest event for each ID
- Instead, it appears to be keeping the OLDEST event (lowest sequence)
- This resets vessel state to their initial positions

### Sample Event Replay Issue

Event log for vessel V-7234:
```
{ id: "V-7234", sequence: 1, state: "queued" }
{ id: "V-7234", sequence: 5, state: "allocated" }
{ id: "V-7234", sequence: 12, state: "departed" }
{ id: "V-7234", sequence: 18, state: "arrived" }
```

**Expected replay result:** `{ id: "V-7234", sequence: 18, state: "arrived" }`

**Actual replay result:** `{ id: "V-7234", sequence: 1, state: "queued" }`

The replay function is keeping the first (oldest) event instead of the last (latest).

### 09:30 UTC - Scope Assessment
- 2,341 vessels affected (27% of active fleet)
- 156 duplicate dispatch orders issued
- 23 berth double-bookings created
- Manual intervention required to correct state

### 14:45 UTC - Resolution
- Event replay disabled
- Manual state correction completed
- Failback to primary datacenter

## Technical Analysis

The event replay deduplication logic compares sequence numbers incorrectly. When deciding whether to update the "latest" event for a given ID:

```
Current logic appears to use: event.sequence < existingEvent.sequence
Correct logic should be:       event.sequence > existingEvent.sequence
```

This inverts the behavior, causing oldest events to be retained instead of newest.

## Impact

| Metric | Count |
|--------|-------|
| Vessels with incorrect state | 2,341 |
| Duplicate orders issued | 156 |
| Berth conflicts created | 23 |
| Manual corrections required | 2,520 |
| SLA breaches | 89 |
| Estimated revenue impact | $340,000 |

## Additional Observations

### Checkpoint Interval Issue
During investigation, we also noticed checkpoints are being created at unexpected intervals. The checkpoint manager has a configured interval of 100 sequences, but checkpoints appear at 101, 201, 301... instead of 100, 200, 300.

```
Expected checkpoint at sequence 100 -> Not created
Checkpoint created at sequence 101 -> Off by one
```

This suggests a boundary comparison issue (> vs >=) in the checkpoint triggering logic.

## Action Items

1. **P1:** Fix event replay sequence comparison to keep latest, not oldest
2. **P2:** Fix checkpoint interval boundary condition
3. **P3:** Add replay convergence tests to CI pipeline
4. **P3:** Implement automated state verification after failover

## Lessons Learned

- Event replay is a critical path that was under-tested
- Sequence comparison direction matters for temporal ordering
- Failover procedures should include state verification step

---

**Attendees:** @resilience-team, @platform-sre, @dispatch-ops
**Next Review:** 2024-09-22
**Status:** Action items in progress
