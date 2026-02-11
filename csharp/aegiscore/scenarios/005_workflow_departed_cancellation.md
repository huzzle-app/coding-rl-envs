# Post-Mortem: Ghost Vessel Incident - MV Northern Star

**Incident ID**: INC-3291
**Date**: 2024-11-10
**Duration**: 4 hours 23 minutes
**Severity**: P2 - Major
**Author**: Maritime Operations Team

---

## Executive Summary

A vessel that had physically departed Rotterdam port was incorrectly marked as "cancelled" in the AegisCore system, causing a cascade of downstream issues including:
- Berth re-allocation to another vessel while departure was in progress
- Conflicting routing instructions sent to vessel
- Customs clearance flags reset
- Pilot dispatch cancelled mid-transit

The root cause was identified as an invalid state transition being allowed by the workflow engine.

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 06:00 | MV Northern Star departs berth B-14 |
| 06:02 | Automatic status update: `allocated -> departed` |
| 06:15 | Operator error: Cancellation request submitted for wrong vessel ID |
| 06:15 | **System accepts transition: `departed -> cancelled`** |
| 06:17 | Berth B-14 marked as available |
| 06:18 | MV Eastern Promise allocated to B-14 |
| 06:23 | Pilot boat recalled from escorting Northern Star |
| 06:45 | Port Control notices vessel still in channel, status shows "cancelled" |
| 07:30 | Manual database correction applied |
| 10:23 | All downstream systems resynchronized |

## Root Cause Analysis

### The Bug

The workflow state machine in AegisCore incorrectly allows the transition `departed -> cancelled`.

According to maritime operations logic:
- Once a vessel has physically departed, the order cannot be cancelled
- The only valid transition from "departed" should be to "arrived"
- Cancellation is only valid from "queued" or "allocated" states

### Why This Matters

The state machine graph defines allowed transitions:
```
queued -> [allocated, cancelled]
allocated -> [departed, cancelled]
departed -> [arrived]  <-- cancelled should NOT be here
arrived -> []
```

The current implementation erroneously includes "cancelled" in the departed state's allowed transitions.

## Impact Analysis

### Operational Impact
- 1 vessel received conflicting instructions
- 1 berth double-booked for 45 minutes
- 2 pilot dispatches wasted
- Customs clearance had to be manually re-processed

### Financial Impact
- Pilot dispatch costs: $4,200
- Berth conflict resolution: $12,500
- Customs delay fees: $8,300
- **Total**: $25,000

### Safety Considerations
- Vessel in channel with cancelled status could have been ignored by traffic control
- Pilot recall during active escort is a safety violation
- No physical incidents occurred (this time)

## Failing Tests

```
WorkflowGraphEnforced (tests invalid transition blocking)
WorkflowDepartedStateFinal (tests departed only goes to arrived)
```

## Corrective Actions

| Action | Owner | Status |
|--------|-------|--------|
| Fix workflow state machine to remove departed->cancelled | Platform Team | Pending |
| Add validation at API layer for extra safety | API Team | Pending |
| Update operator training on vessel ID verification | Ops Manager | Complete |
| Add confirmation dialog for cancellation of active orders | UX Team | Pending |

## Lessons Learned

1. State machine definitions should be reviewed against business logic requirements
2. Physical-world state (vessel location) must constrain system state transitions
3. Operator error is inevitable; system must prevent invalid states regardless

---

**Bug Reference**: AGS0018
**Related Module**: Workflow.cs
**Review Date**: 2024-11-17
