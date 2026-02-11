# Customer Escalation: Data Corruption During Sync

## Zendesk Ticket #47829

**Priority**: Urgent
**Customer**: Acme Corp (Enterprise Tier)
**Account Value**: $240,000 ARR
**CSM**: Jennifer Walsh
**Created**: 2024-01-14 14:32 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We've been experiencing serious issues with CloudVault sync over the past week. Multiple users in our organization are seeing corrupted or missing data when syncing between devices. This is affecting our daily operations and we need this resolved immediately.

### Reported Symptoms

1. **Duplicate Sync Sessions**: Users report seeing "sync already in progress" errors even though they haven't initiated a sync recently.

2. **Lost Changes**: Files edited on Device A sometimes don't appear on Device B, or appear with stale content.

3. **Intermittent Panics**: Our desktop client logs show occasional crashes with "assignment to nil map" errors.

4. **Conflict Resolution Failures**: When conflicts are detected, attempting to register a custom resolution strategy crashes the sync service.

---

## Technical Details from Customer Logs

### Desktop Client Logs (Windows)

```
2024-01-14T10:23:45.123Z [SYNC] Starting sync for device LAPTOP-A1B2C3
2024-01-14T10:23:45.125Z [SYNC] Fetching changes since 2024-01-14T09:00:00Z
2024-01-14T10:23:45.342Z [SYNC] Received 15 remote changes
2024-01-14T10:23:45.343Z [SYNC] Applying changes locally...
2024-01-14T10:23:45.891Z [ERROR] Sync failed: sync already in progress
2024-01-14T10:23:45.892Z [SYNC] Retrying in 30 seconds...
```

### Desktop Client Logs (macOS)

```
2024-01-14T10:24:12.567Z [SYNC] Starting sync for device MACBOOK-X9Y8Z7
2024-01-14T10:24:12.789Z [SYNC] GetSyncStatus returned error: internal error
2024-01-14T10:24:13.001Z [SYNC] Applying change: update /documents/quarterly-report.xlsx
2024-01-14T10:24:13.234Z [CONFLICT] Detected conflict on file quarterly-report.xlsx
2024-01-14T10:24:13.235Z [CONFLICT] Attempting automatic resolution...
panic: assignment to entry in nil map

goroutine 847 [running]:
cloudvault/sync.(*ConflictResolver).RegisterStrategy(...)
    /src/sync/conflict.go:122 +0x45
```

### Server-Side Error Logs (from customer's CloudVault audit log export)

```
{"level":"error","ts":"2024-01-14T10:23:45.890Z","msg":"race detected in sync state access","user_id":"usr_abc123","device":"LAPTOP-A1B2C3"}
{"level":"warn","ts":"2024-01-14T10:24:13.233Z","msg":"pending changes map nil","user_id":"usr_def456"}
{"level":"error","ts":"2024-01-14T10:24:45.001Z","msg":"failed to apply delete change","error":"nil error returned"}
```

---

## Internal Slack Thread

**#eng-support** - January 14, 2024

**@jennifer.walsh** (14:45):
> Hey team, I have Acme Corp on fire about sync issues. They're seeing data corruption and their desktop client is crashing. This is their 3rd escalation this month. Can someone take a look urgently?

**@dev.marcus** (14:52):
> Looking at their logs now. The "sync already in progress" error suggests we have concurrent access issues in the sync state management. Let me check if we're locking properly.

**@dev.marcus** (15:03):
> Found something interesting. In `sync.go`, we read from `syncStates` map without holding the mutex in several places. That would explain the race conditions.

**@dev.sarah** (15:10):
> I see the conflict resolver issue too. The `strategies` map is never initialized in `NewConflictResolver`. Any attempt to register a strategy will panic.

**@dev.marcus** (15:15):
> Also, in `StartSync`, we initialize `SyncState` but never initialize the `PendingChanges` map inside it. That nil map is going to bite us later.

**@jennifer.walsh** (15:20):
> How widespread is this? Is this affecting all customers or just Acme?

**@dev.marcus** (15:25):
> Theoretically all customers, but it's a race condition so it's probabilistic. Acme probably hits it more because they have heavy multi-device usage with frequent syncs.

**@sre.kim** (15:30):
> I'm seeing race detector warnings in our test runs too. We should probably run `go test -race` and fix everything that shows up.

---

## Reproduction Steps (from QA)

1. Set up two devices syncing the same account
2. Start sync operations on both devices simultaneously
3. Observe "sync already in progress" errors on one device
4. Create a file conflict by editing the same file on both devices before sync completes
5. Attempt to resolve conflict with a custom strategy
6. Observe nil map panic

**Success Rate**: ~30-40% reproduction rate with concurrent operations

---

## Additional Context

The customer mentioned they recently rolled out CloudVault to their entire sales team (200+ users), which increased their device count from ~50 to ~400. The issues started becoming noticeable around the same time.

---

## Impact Assessment

- **Users Affected**: ~400 devices at Acme Corp
- **Data Loss Risk**: Medium - changes may be silently dropped
- **Revenue Risk**: Customer considering alternative solutions
- **SLA Status**: At risk of breach (99.9% uptime, currently at 98.7% due to related issues)

---

## Files to Investigate

Based on the stack traces and error patterns:
- `internal/services/sync/sync.go` - Race conditions in state management
- `internal/services/sync/conflict.go` - Nil map panics in conflict resolution

---

**Assigned**: @dev.marcus, @dev.sarah
**Deadline**: EOD January 15, 2024
**Follow-up Call**: Scheduled with customer for January 16, 2024 09:00 PST
