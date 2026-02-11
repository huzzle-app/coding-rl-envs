# Incident Report: INC-2024-1903

**Severity**: P1 - Critical
**Status**: Open
**Reported By**: Resilience Engineering - STRATAGUARD-SRE
**Date**: 2024-11-17 14:22 UTC
**Affected System**: StrataGuard Resilience Replay Engine

---

## Executive Summary

The deterministic replay system is selecting the WRONG sequence number when deduplicating events, causing state corruption during failover recovery. Instead of keeping the latest (highest sequence) event, the system retains the earliest (lowest sequence) event.

## Timeline

- **14:02 UTC**: Planned failover initiated from primary to secondary datacenter
- **14:04 UTC**: Replay engine begins processing event log
- **14:08 UTC**: Operators report state inconsistencies after recovery
- **14:15 UTC**: Investigation reveals replay selected outdated events
- **14:22 UTC**: P1 incident declared - data integrity at risk

## Symptoms

1. `Resilience.Replay()` keeps events with LOWER sequence numbers instead of HIGHER
2. State after replay does not match expected final state
3. Test `ReplayLatestSequenceWins` failing:
   ```
   Expected: Sequence=2 for event "x"
   Actual: Sequence=1 for event "x"
   ```

## Impact

- **Data Integrity**: Inconsistent state across 12 entity records
- **Operational**: Manual reconciliation required for affected workflows
- **Availability**: Recovery procedure extended by 47 minutes

## Affected Tests

```
FAILED: CoreTests.ReplayLatestSequenceWins
FAILED: CoreTests.ReplayConvergence
FAILED: HyperMatrixTests.HyperMatrixCase (replay assertions, ~540 cases)
```

## Log Excerpt

```
2024-11-17T14:04:12.334Z [INFO] resilience.replay: Processing event stream
  event_count=1847 unique_entities=412

2024-11-17T14:04:12.891Z [DEBUG] resilience.replay: Dedup decision
  entity_id="k-7" incoming_seq=2 existing_seq=1
  action="KEEP_EXISTING"  <-- WRONG! Should replace with newer

2024-11-17T14:08:45.002Z [ERROR] recovery.validation: State mismatch detected
  entity_id="k-7" expected_seq=2 actual_seq=1
  checksum_mismatch=true

2024-11-17T14:15:01.447Z [ALERT] ops.integrity: Data corruption suspected
  affected_entities=12 recovery_mode="manual"
```

## Reproduction

```csharp
var replayed = Resilience.Replay([
    new ReplayEvent("x", 1),  // First event, seq=1
    new ReplayEvent("x", 2),  // Later event, seq=2 (should win)
    new ReplayEvent("y", 1)
]);

// Expected: Event "x" has Sequence=2 (latest wins)
// Actual: Event "x" has Sequence=1 (earliest wins - WRONG!)
```

## Business Context

The replay engine is critical for:
- **Disaster Recovery**: Rebuilding state after failover
- **Idempotency**: Ensuring reprocessed events don't corrupt state
- **Audit Trail**: Maintaining accurate event history

The comparison operator appears inverted. When multiple events share the same ID, the system should retain the one with the HIGHEST sequence number (most recent), not the LOWEST.

## Recovery Actions Taken

1. Manual state reconciliation for 12 affected entities
2. Replay disabled until root cause resolved
3. Checksum validation enabled for all state transitions

---

**Assigned To**: Resilience Engineering
**Target Resolution**: 2024-11-17 18:00 UTC
**Related Incidents**: INC-2024-1891 (similar pattern observed)
