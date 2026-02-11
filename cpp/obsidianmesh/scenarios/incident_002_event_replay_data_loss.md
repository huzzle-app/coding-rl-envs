# INC-2024-0923: Critical Event Data Loss During Replay Recovery

**Severity**: P1 - Critical
**Status**: Investigating
**Created**: 2024-03-18 14:22 UTC
**Component**: Resilience / Event Replay
**Affected Services**: resilience, audit, analytics

---

## Executive Summary

A network partition at 13:45 UTC triggered automated replay recovery procedures. Upon recovery, audit logs revealed significant data gaps. Approximately 23% of events from the affected window are missing or corrupted. Financial reconciliation for Q1 close is blocked.

Regulatory exposure: SOX compliance audit scheduled for 2024-03-25.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 13:45 | Network partition detected between US-EAST and EU-WEST |
| 13:47 | Automatic failover initiated |
| 14:02 | Partition resolved, replay recovery started |
| 14:15 | Recovery "completed" - systems report healthy |
| 14:22 | Audit team reports missing transaction records |
| 14:35 | Incident escalated to P1 |

---

## Symptoms

1. **Events Missing from Replay Window**
   - Replay window filtering appears to exclude boundary events
   - Events at exactly `from_seq` are not included in replay
   - ~4,200 events missing from boundary sequences

2. **Event Log Corruption**
   - New events being appended cause oldest events to be lost
   - EventLog appears to evict from wrong end
   - Audit trail broken for vessels: V-8821, V-8834, V-8847 (and 127 others)

3. **Duplicate Events in Output**
   - Idempotency checks are not detecting duplicates
   - Same events appearing 3-4 times in downstream systems
   - Billing discrepancies reported by finance

4. **Event Compaction Keeping Wrong Records**
   - When compacting to keep most recent per ID, system keeps oldest instead
   - Stale dispatch instructions being processed

---

## Test Failures Observed

```
FAILED: resilience_replay_window
  With events [a@1, b@2, c@3, d@4], from_seq=1, to_seq=3
  Expected: 3 events (sequences 1, 2, 3)
  Actual: 2 events (sequences 2, 3 only)

FAILED: resilience_idempotent
  Expected: false for duplicate IDs [{a,1}, {a,2}]
  Actual: true (always returns true)

FAILED: resilience_compact
  For events [{a,1}, {a,2}, {b,3}] with max_per_id=1
  Expected: keep {a,2} (latest for 'a') and {b,3}
  Actual: keeping {a,1} (first for 'a') instead

FAILED: events_dedup
  Expected: keep earliest timestamp per ID
  Actual: keeping latest timestamp per ID
```

---

## Investigation Notes

### Replay Window Boundary Analysis
```
Replay request: from_seq=1000, to_seq=1050
Expected events: sequences 1000, 1001, ..., 1050 (51 events)
Actual events: sequences 1001, 1002, ..., 1050 (50 events)

The boundary at from_seq is being excluded (> instead of >=)
```

### EventLog Eviction Behavior
```cpp
// Log analysis shows:
// EventLog max_size: 10000
// Before append: 10000 events (seq 5000-14999)
// After append of seq 15000: 10000 events (seq 5000-14999)
// Expected: events (seq 5001-15000)
//
// The newest event is being evicted instead of oldest
```

### Idempotency Check
The `is_idempotent_safe()` function appears to always return true, regardless of whether duplicate event IDs exist. This allows replay to insert duplicates.

---

## Data Impact Assessment

| Data Category | Records Affected | Recovery Status |
|---------------|------------------|-----------------|
| Vessel positions | 4,247 | Partial - GPS logs available |
| Dispatch orders | 1,834 | Blocked - authoritative source |
| Billing events | 892 | Critical - financial impact |
| Audit trail | 3,421 | Critical - compliance |

---

## Affected Tests

- `resilience_replay_window` - Boundary inclusion
- `resilience_idempotent` - Duplicate detection
- `resilience_compact` - Event compaction order
- `events_dedup` - Deduplication by timestamp
- `EventLog::append` - Eviction order

---

## Recovery Plan

1. **Immediate**: Disable automated replay until fixed
2. **Short-term**: Manual reconciliation from backup tapes
3. **Long-term**: Fix underlying bugs, replay full audit window

---

## Compliance Notes

- SOX audit in 7 days requires complete audit trail
- Legal has been notified of potential gaps
- External auditors to be briefed on Tuesday

---

## References

- Related: `src/resilience.cpp` - replay functions
- Related: `src/events.cpp` - EventLog and dedup
- Audit Dashboard: https://audit.obsidianmesh.internal/gaps
- DR Runbook: https://wiki.internal/dr/event-replay
