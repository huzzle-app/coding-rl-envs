# Incident Report: Real-Time Collaboration Data Loss

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-22 14:32 UTC
**Acknowledged**: 2024-01-22 14:35 UTC
**Team**: Real-Time Collaboration

---

## Alert Details

```
CRITICAL: Document collaboration consistency check failing
Host: cloudmatrix-presence-prod-1.us-west-2.internal
Service: presence-service
Metric: document_divergence_count
Threshold: >10 divergent docs per 5 minutes
Current Value: 847
```

## Timeline

**14:32 UTC** - Alert fired: High document divergence rate detected

**14:38 UTC** - Customer complaints flooding support queue:
> "My teammate and I are both editing the Q4 report. We see different versions even though we're both looking at the same document!"

**14:45 UTC** - Engineering confirms issue is widespread across multiple documents

**14:52 UTC** - Temporary mitigation: Disabled auto-merge, forcing manual refresh

**15:10 UTC** - Customer reports continued issues with cursor positions being "wrong"

**15:30 UTC** - Additional reports: Undo operations are undoing other users' changes

## Customer Reports

### Zendesk Ticket #89234

> We have 5 team members editing our quarterly presentation simultaneously. Here's what we're seeing:
>
> 1. User A types "quarterly revenue" at position 100
> 2. User B types "annual expenses" at position 150 at the exact same time
> 3. After sync, User A sees: "quarterly revenueal expenses" (mangled text)
> 4. User B sees: "annual expensesquarterly revenue" (different mangling)
>
> The document is now corrupted and neither version matches what either person typed. We had to revert to a backup from 2 hours ago.

### Zendesk Ticket #89256

> Really weird cursor behavior. My cursor says I'm at line 45, character 12. But when I type, the text appears somewhere around line 42. It's like my cursor position isn't being tracked correctly.
>
> Also, when I click to move my cursor, other people's cursors all seem to jump to random positions momentarily.

### Zendesk Ticket #89271

> URGENT: Undo is broken!
>
> I was editing section 3 of our doc. My teammate was editing section 7. When my teammate pressed Ctrl+Z to undo their change, it undid MY change in section 3 instead!
>
> We've now lost 30 minutes of work because we can't trust undo anymore.

## Grafana Dashboard Observations

### Merge Conflict Resolution

```
Time: 14:00 - 15:00 UTC
Metric: crdt_merge_conflicts_total

14:00  12 conflicts/min
14:15  234 conflicts/min
14:30  1,892 conflicts/min (anomaly start)
14:45  3,456 conflicts/min
15:00  4,012 conflicts/min
```

### Document State Divergence

```
Metric: document_checksum_mismatches

Normally: 0-2 per hour (network glitches)
Current: 847 in last 5 minutes

Pattern: All mismatches involve documents with 3+ concurrent editors
```

### Operation Transform Failures

```
Metric: ot_transform_errors

Error types observed:
- "Transform not commutative": 342 occurrences
- "Operation ordering conflict": 567 occurrences
- "Position offset mismatch": 234 occurrences
```

## Technical Investigation

### Reproduction Steps (from QA)

1. Open document with 2+ users
2. Both users type at the same time at different positions
3. Wait for sync (100-500ms)
4. Observe: Document content differs between users

**Reproduction rate**: 100% with concurrent edits at same timestamp

### Server Logs

```
2024-01-22T14:32:18.123Z [presence] WARN: CRDT merge produced different results
  local_state: "Hello world, this is a test"
  remote_state: "Hello world, this is a test"
  merged_local: "Hello world, this is a different test"
  merged_remote: "Hello world, this is a test different"

2024-01-22T14:32:18.456Z [presence] ERROR: Cursor position drift detected
  reported_position: 145
  actual_position: 138
  drift: -7 characters

2024-01-22T14:32:19.789Z [presence] WARN: Undo stack corruption
  user_id: user_abc123
  expected_undo_owner: user_xyz789
  actual_operation_owner: user_abc123
```

### Client-Side Console Logs

```javascript
// From customer's browser console
[CloudMatrix] Received remote operation: {type: "insert", position: 100, content: "quarterly revenue"}
[CloudMatrix] Received remote operation: {type: "insert", position: 150, content: "annual expenses"}
[CloudMatrix] Transforming operations...
[CloudMatrix] Transform result: position 150 -> 165 (expected 167)
[CloudMatrix] WARNING: Operations may have diverged due to same-timestamp conflict
```

## Impact Assessment

- **Users Affected**: ~2,400 active collaboration sessions
- **Documents Corrupted**: 847 with divergent state
- **Data Loss**: Unknown - some customers reporting lost paragraphs
- **SLA Status**: Critical - real-time collaboration is core feature

## Suspected Areas

Based on symptoms, engineering suspects issues in:
- CRDT merge logic (concurrent edit handling)
- Operational transform composition
- Cursor position tracking after remote operations
- Undo/redo stack management (per-user vs shared stack)

## Files Mentioned in Stack Traces

- `shared/realtime/index.js` - CRDT and OT implementation
- `services/presence/src/services/presence.js` - Cursor tracking

---

**Status**: INVESTIGATING
**Assigned**: @collab-team
**Follow-up**: Customer bridge call at 16:00 UTC
