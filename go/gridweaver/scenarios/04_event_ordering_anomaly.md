# Alert Investigation: Event Processing Anomalies in Demand Response System

**Alert ID**: MON-2024-1156
**Source**: Datadog APM / Custom GridWeaver Monitors
**Triggered**: 2024-03-22 18:47:33 UTC
**Investigating Engineer**: Operations On-Call

---

## Alert Summary

Multiple monitors triggered simultaneously indicating event processing anomalies:

```
[CRITICAL] gridweaver.events.sequence_gaps > 100 (current: 347)
[WARNING]  gridweaver.events.duplicate_ratio > 0.05 (current: 0.31)
[WARNING]  gridweaver.events.wrong_region_match > 0 (current: 89)
[ERROR]    gridweaver.demandresponse.dispatch_count mismatch
```

## Investigation Log

### 18:52 UTC - Initial Triage

Checked event pipeline metrics dashboard. Key observations:

**Event Ordering Issues:**
Events arriving with sequence numbers [1, 2, 3, 5, 4, 8, 7, 6, 9] are being processed in order [9, 8, 7, 6, 5, 4, 3, 2, 1] - completely reversed!

The SortBySequence function appears to be sorting descending instead of ascending.

### 19:05 UTC - Duplicate Handling Investigation

DeduplicateEvents is keeping the wrong occurrence when duplicates exist.

Test case:
```
Input Events:
  - {ID: "evt-001", Sequence: 10, Data: "original"}
  - {ID: "evt-002", Sequence: 20, Data: "unique"}
  - {ID: "evt-001", Sequence: 30, Data: "duplicate-updated"}

Expected (keep first): [{ID: "evt-001", Seq: 10, Data: "original"}, {ID: "evt-002"...}]
Actual (keeping last):  [{ID: "evt-001", Seq: 30, Data: "duplicate-updated"}, {ID: "evt-002"...}]
```

In an eventually-consistent system, keeping the last occurrence means late-arriving retransmissions overwrite the original events.

### 19:18 UTC - Region Filtering Bug

FilterByRegion is matching prefixes instead of exact values:

```
Filter: region="west"
Events:
  - {Region: "west", ...} - SHOULD match, DOES match (correct)
  - {Region: "western", ...} - should NOT match, DOES match (BUG)
  - {Region: "midwest", ...} - should NOT match, does NOT match (correct)
  - {Region: "west-coast", ...} - should NOT match, DOES match (BUG)
```

Any region starting with the filter string is incorrectly included.

### 19:25 UTC - Event Type Filtering Inverted

FilterByType is returning events that DON'T match the specified type:

```
Filter: eventType="DISPATCH_COMMAND"
Input: 100 events (30 DISPATCH_COMMAND, 70 other types)
Expected: 30 events
Actual: 70 events (everything EXCEPT DISPATCH_COMMAND)
```

### 19:33 UTC - Window Boundary Bug

WindowEvents is excluding events exactly at the lower boundary:

```
Window: minSeq=100, maxSeq=200
Event with Sequence=100: EXCLUDED (should be included)
Event with Sequence=150: included
Event with Sequence=200: included
Event with Sequence=99: excluded (correct)
```

Off-by-one on the lower bound.

### 19:41 UTC - LastEventPerRegion Returning First

Function is supposed to return the most recent event per region, but it's returning the oldest:

```
Events for region "east":
  - Sequence 10 (oldest)
  - Sequence 50
  - Sequence 90 (newest)

Expected LastEventPerRegion["east"]: Sequence 90
Actual: Sequence 10
```

### 19:48 UTC - CountByType Not Counting by Type

The CountByType function returns a single count for "all" events instead of grouping by type:

```
Input: [DISPATCH x 5, FORECAST x 3, ALERT x 2]
Expected: {"DISPATCH": 5, "FORECAST": 3, "ALERT": 2}
Actual: {"all": 10}
```

### 19:55 UTC - Sequence Gap Calculation Wrong

SequenceGaps is adding sequence numbers instead of finding the difference:

```
Events: Sequence [10, 20, 30]
Expected gaps: [10, 10] (20-10=10, 30-20=10)
Actual gaps: [30, 50] (10+20=30, 20+30=50)
```

### 20:05 UTC - Demand Response Service Issues

Related issues in the demand response service:

**DispatchCount returning capacity, not length:**
```
Dispatched IDs: ["DR-001", "DR-002", "DR-003"]
Slice length: 3
Slice capacity: 100 (initial allocation)
DispatchCount(): 100 (wrong - should be 3)
```

**Duplicate dispatch IDs accepted:**
```
RecordDispatch("DR-001") - OK
RecordDispatch("DR-002") - OK
RecordDispatch("DR-001") - Should fail, but succeeds (duplicate)
Dispatched list: ["DR-001", "DR-002", "DR-001"]
```

### 20:15 UTC - Outage Service Problems

Similar patterns in outage tracking:

**ReportOutage accepts duplicates:**
```
ReportOutage("OUT-001") - OK
ReportOutage("OUT-001") - Should fail, succeeds
Active outages: ["OUT-001", "OUT-001"]
```

**ResolveOutage always returns success:**
```
ResolveOutage("OUT-999") - ID doesn't exist
Expected: false
Actual: true
```

## Impact Assessment

1. **Event misordering**: Commands executing in wrong sequence, causing grid state desynchronization
2. **Wrong region matching**: Events from "western" region being processed by "west" region handler
3. **Type filter inversion**: Dispatch commands being dropped, non-dispatch events being processed as commands
4. **Duplicate contamination**: Retransmitted events overwriting original data
5. **Dispatch count errors**: Capacity planning using wrong DR resource availability
6. **Gap detection failure**: Missing events not being detected for replay

## Affected Components

- `internal/events/pipeline.go` - Event ordering and filtering
- `services/demandresponse/service.go` - DR dispatch tracking
- `services/outage/service.go` - Outage reporting and resolution

## Recommended Actions

1. Halt automated DR dispatch until event ordering is verified
2. Review event pipeline sorting and filtering logic
3. Check boundary conditions in window functions
4. Verify duplicate detection keeps first occurrence, not last
5. Ensure type filtering uses equality, not inequality

---

**Status**: Under active investigation
**Escalated To**: Platform Engineering Lead
**Next Update**: 2024-03-22 22:00 UTC
