# Incident Report: Real-time Sync Failures in Production

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-12 14:23 UTC
**Acknowledged**: 2024-02-12 14:26 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: CollabCanvas sync failure rate exceeding threshold
Service: collabcanvas-api-prod
Metric: websocket.sync.failure_rate
Threshold: >5% for 5 minutes
Current Value: 23.7%
```

## Timeline

**14:23 UTC** - Initial alert fired for high sync failure rate

**14:28 UTC** - Customer complaints start appearing in support queue

**14:35 UTC** - Multiple enterprise customers report "changes not appearing for other users"

**14:42 UTC** - One customer reports losing 30 minutes of collaborative work

**14:50 UTC** - Identified pattern: failures spike during high-concurrency editing sessions

## Customer Reports

### Enterprise Customer: Acme Design Co.

> "We have 8 designers working on the same board right now. People keep complaining their changes disappear or others can't see their updates. Sometimes changes appear minutes later, sometimes never. We're losing work and this is blocking a client deadline."

### Enterprise Customer: TechCorp Marketing

> "Our team was in a live meeting presenting a whiteboard. The changes the presenter made weren't showing up for meeting attendees. Very embarrassing. We had to switch to a competitor's tool mid-meeting."

### Individual User Report

> "I drew a diagram, watched it save (spinner completed), then my colleague in the same room said they don't see it. When I refreshed, it was gone. Had to redo it 3 times."

## Datadog Dashboard Observations

### Sync Operations

```
Time Window: 14:00-15:00 UTC

sync.update.initiated: 12,847
sync.update.confirmed: 9,234
sync.update.lost: 3,613 (28.1%)

websocket.broadcast.sent: 48,291
websocket.broadcast.confirmed: 37,102
websocket.broadcast.timeout: 11,189
```

### Redis Pub/Sub Metrics

```
redis.publish.calls: 48,291
redis.publish.success: 48,291  (looks fine)
redis.subscribe.received: 37,102  (mismatch!)

Note: Gap between publish and receive suggests messages aren't being awaited properly
```

### Board State Consistency

```
state.version.mismatch_detected: 847 occurrences
concurrent.update.race_condition: 234 occurrences
```

## Application Logs

```
2024-02-12T14:23:45.123Z [SYNC] Update initiated board=b-a1b2c3d4 element=e-x1y2z3
2024-02-12T14:23:45.124Z [SYNC] Broadcast queued board=b-a1b2c3d4
2024-02-12T14:23:45.125Z [SYNC] Function returned success=true
# Note: No log confirming broadcast completion before function return

2024-02-12T14:24:12.567Z [SYNC] Update initiated board=b-a1b2c3d4 element=e-p9q8r7
2024-02-12T14:24:12.568Z [SYNC] State read version=142
2024-02-12T14:24:12.569Z [SYNC] Update initiated board=b-a1b2c3d4 element=e-m4n5o6
2024-02-12T14:24:12.569Z [SYNC] State read version=142  # Same version!
2024-02-12T14:24:12.571Z [SYNC] State written version=143
2024-02-12T14:24:12.572Z [SYNC] State written version=143  # Both wrote version 143!
```

## Reproduction Steps (from QA)

### Scenario 1: Lost Broadcasts

1. Open board in two browser windows
2. Make rapid changes in Window A
3. Observe that ~30% of changes don't appear in Window B
4. If you wait 100ms between changes, success rate improves to ~95%

### Scenario 2: Race Conditions

1. Open board in three browser windows
2. In each window, simultaneously draw a shape
3. Observe inconsistent state across windows
4. Some windows show 2 shapes, some show 3
5. Refreshing all windows shows different element counts

**Success Rate**: 100% reproduction with concurrent operations

## Technical Analysis

### Suspected Issue 1: Async Operation Not Awaited

In `src/services/canvas/sync.service.js`, the `broadcastUpdate` function appears to return before the Redis publish completes:

```
# Pseudocode showing the pattern:
async broadcastUpdate(boardId, operation) {
  io.emit('element-update', operation);
  redis.publish('board-updates', data);  // Missing await?
  return { success: true };  // Returns immediately
}
```

### Suspected Issue 2: Race Condition in State Updates

Multiple updates reading the same state version simultaneously, then each incrementing it, resulting in lost updates:

```
Thread A: read version 142 -> increment -> write version 143
Thread B: read version 142 -> increment -> write version 143  # Overwrites A's changes
```

## Vector Clock Comparison Issue

During investigation, we also noticed strange behavior with CRDT conflict detection:

```
2024-02-12T14:35:22.111Z [CRDT] Comparing clocks
2024-02-12T14:35:22.112Z [CRDT] clock1: {"node-a": "10", "node-b": "2"}
2024-02-12T14:35:22.113Z [CRDT] clock2: {"node-a": "9", "node-b": "3"}
2024-02-12T14:35:22.114Z [CRDT] Result: concurrent (expected: clock1 > clock2)
```

Note: Values coming from JSON parsing are strings, but `'10' > '9'` is false in JavaScript string comparison!

## Attempted Mitigations

1. **Increased WebSocket timeouts** - No improvement
2. **Added retry logic on client** - Helped mask symptoms but not root cause
3. **Scaled Redis cluster** - No change (messages are being published)

## Questions for Investigation

1. Are we awaiting all async Redis operations before returning?
2. Is there locking/mutex around concurrent state updates?
3. Are vector clock values being compared as strings instead of numbers?

## Impact Assessment

- **Users Affected**: ~2,400 active users during incident window
- **Data Loss**: Estimated 3,600+ lost edits
- **Revenue Risk**: 2 enterprise customers threatened to cancel
- **SLA Status**: Breaching 99.9% availability SLA

## Files to Investigate

Based on the patterns observed:
- `src/services/canvas/sync.service.js` - Async operations and state management
- `src/services/canvas/crdt.service.js` - Vector clock comparison logic

---

**Status**: INVESTIGATING
**Assigned**: @sync-team
**Follow-up**: Customer call scheduled for 2024-02-12 18:00 UTC
