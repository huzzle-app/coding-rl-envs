# Scenario 003: Disaster Recovery Replay Produces Inconsistent State

## Type: Post-Incident Review (PIR)

## Incident ID: PIR-2024-0892

## Date: 2024-11-15

---

## Executive Summary

During a planned failover test to our DR site, the event replay mechanism produced a different final state than the primary site. This caused 47 dispatch records to show incorrect vessel positions and 12 manifests to have wrong cargo allocations.

---

## Background

SignalDock uses event sourcing for disaster recovery. Events are replayed through the `replay()` function to reconstruct system state. By design, replaying the same events (even in different arrival order) should produce identical final state.

---

## What Happened

### Test Procedure
1. Captured event stream from primary site (2,847 events)
2. Sent same events to DR site in randomized order (simulating network reordering)
3. Compared final state between sites

### Expected Result
Identical vessel positions, manifest states, and dispatch records on both sites.

### Actual Result
47 dispatch records differed between sites. Investigation showed:

**Primary site event order:**
```
Event A: vessel-123, sequence: 100
Event B: vessel-123, sequence: 150
Event C: vessel-123, sequence: 150 (duplicate seq, later arrival)
```

**DR site event order:**
```
Event C: vessel-123, sequence: 150 (arrived first)
Event A: vessel-123, sequence: 100
Event B: vessel-123, sequence: 150 (duplicate seq, later arrival)
```

**Expected behavior:** Both sites should keep Event B (or Event C) consistently for sequence 150.

**Actual behavior:** Primary kept Event C, DR kept Event B. The `replay()` function is not handling duplicate sequence numbers deterministically.

---

## Technical Analysis

When two events have the same sequence number:
- The deduplication logic uses `>=` comparison
- This means "equal or greater" replaces the existing event
- Result: the LAST event with a given sequence wins
- But "last" depends on arrival order, breaking determinism

Additionally, the final sorted output appears to be in DESCENDING order (newest first) rather than ascending (oldest first), which affects downstream consumers expecting chronological order.

---

## Impact

- DR site unusable for 4 hours during reconciliation
- 47 dispatch records required manual correction
- Confidence in DR procedures severely impacted
- Regulatory audit finding likely

---

## Files to Investigate

- `src/core/resilience.js` - `replay()` function
- Event deduplication logic
- Final sort order of replayed events

---

## Questions

1. Should equal sequence numbers keep the FIRST or LAST event seen?
2. What is the expected sort order of the replay output?
3. Are there other functions relying on replay determinism?
