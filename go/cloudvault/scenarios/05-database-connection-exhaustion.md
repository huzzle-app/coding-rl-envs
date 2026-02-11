# Grafana Alert: Database Connection Pool Exhausted

## Alert Details

**Alert Name**: PostgreSQL Connection Pool Exhausted
**Severity**: Critical
**Firing Since**: 2024-01-15 07:23 UTC
**Dashboard**: CloudVault Infrastructure > Database

---

## Alert Configuration

```yaml
alert: PostgresConnectionPoolExhausted
expr: pg_stat_activity_count{datname="cloudvault"} >= 25
for: 2m
labels:
  severity: critical
annotations:
  summary: "All database connections in use"
  description: "Connection count {{ $value }} has reached pool limit of 25"
```

## Current Metrics

| Metric | Value | Threshold |
|--------|-------|-----------|
| Active Connections | 25 | 25 (max) |
| Idle Connections | 0 | - |
| Waiting Queries | 147 | - |
| Avg Query Time | 12.3s | <1s |
| Failed Connections | 892 | - |

---

## Error Logs from Application

```
2024-01-15T07:23:14Z ERROR failed to acquire connection: connection pool exhausted
2024-01-15T07:23:14Z ERROR request failed path=/api/v1/files error="pq: connection pool exhausted"
2024-01-15T07:23:15Z ERROR failed to acquire connection: connection pool exhausted
2024-01-15T07:23:15Z WARN  connection wait timeout after 30s
2024-01-15T07:23:16Z ERROR request failed path=/api/v1/files/search error="context deadline exceeded"
...
[892 similar errors in the past 5 minutes]
```

## PostgreSQL `pg_stat_activity` Output

```sql
SELECT pid, state, query, query_start, wait_event
FROM pg_stat_activity
WHERE datname = 'cloudvault' AND state != 'idle'
ORDER BY query_start;
```

Results:
```
 pid  | state  |                     query                      |       query_start       | wait_event
------+--------+------------------------------------------------+-------------------------+------------
 1234 | active | SELECT id, user_id, name... FROM files WHERE  | 2024-01-15 07:15:22.123 | ClientRead
 1235 | active | SELECT id, user_id, name... FROM files WHERE  | 2024-01-15 07:16:45.456 | ClientRead
 1236 | active | SELECT id, user_id, name... FROM files WHERE  | 2024-01-15 07:17:01.789 | ClientRead
 1237 | active | SELECT COALESCE(MAX(version)... FROM file_ve  | 2024-01-15 07:18:32.012 | ClientRead
 1238 | active | SELECT id, user_id, name... FROM files WHERE  | 2024-01-15 07:19:55.345 | ClientRead
...
[25 rows total, most waiting on ClientRead]
```

## Observations

1. **Long-lived queries**: Many queries started 5+ minutes ago are still "active" but waiting on `ClientRead`
2. **Pattern**: Most stuck queries are `SELECT` statements on the `files` table
3. **Rows not closed**: The queries appear to be waiting for the client to read more data (suggesting `rows.Next()` iteration incomplete)

---

## Application Stack Traces

Thread dump from `SIGQUIT`:

```
goroutine 15234 [IO wait, 312 seconds]:
internal/repository.(*FileRepository).GetByUserID(0xc0001a2000, {0x1a9f5e0, 0xc0003a8000}, {0xc0001bc0c0, 0x10, 0x10})
    /app/internal/repository/file_repo.go:88 +0x1a7

goroutine 15298 [IO wait, 287 seconds]:
internal/services/versioning.(*Service).GetVersions(0xc0002bc000, {0x1a9f5e0, 0xc0003a8100}, {0xc0001bc1e0, 0x10, 0x10})
    /app/internal/repository/versioning/version.go:108 +0x1c3
```

---

## Recent Code Analysis

Examining the hotspot files mentioned in stack traces:

### file_repo.go - GetByUserID (lines 86-116)

```go
func (r *FileRepository) GetByUserID(ctx context.Context, userID uuid.UUID) ([]models.File, error) {
    rows, err := r.db.QueryContext(ctx, `SELECT ... FROM files WHERE user_id = $1`, userID)
    if err != nil {
        return nil, fmt.Errorf("failed to query files: %w", err)
    }
    // NOTE: No defer rows.Close() here!

    var files []models.File
    for rows.Next() {
        var file models.File
        err := rows.Scan(...)
        if err != nil {
            return nil, fmt.Errorf("failed to scan file: %w", err)
            // ^^ Early return without closing rows!
        }
        files = append(files, file)
    }

    // rows.Err() not checked
    rows.Close()  // Only closed at the very end, not on error paths

    return files, nil
}
```

### version.go - GetVersions (lines 102-133)

```go
func (s *Service) GetVersions(ctx context.Context, fileID uuid.UUID) ([]models.FileVersion, error) {
    rows, err := s.db.QueryContext(ctx, `SELECT ... FROM file_versions WHERE file_id = $1`, fileID)
    if err != nil {
        return nil, fmt.Errorf("failed to query versions: %w", err)
    }
    defer rows.Close()  // This is here, but...

    var versions []models.FileVersion
    for rows.Next() {
        var v models.FileVersion
        err := rows.Scan(...)
        if err != nil {
            continue  // Silently continues, never returns - rows stay open!
        }
        versions = append(versions, v)
    }

    // rows.Err() not checked!
    return versions, nil
}
```

### BulkCreate Transaction Issue (lines 252-280)

```go
func (r *FileRepository) BulkCreate(ctx context.Context, files []models.File) error {
    tx, err := r.db.BeginTx(ctx, nil)
    if err != nil {
        return fmt.Errorf("failed to begin transaction: %w", err)
    }
    defer tx.Rollback()

    for _, file := range files {
        stmt, err := tx.PrepareContext(ctx, `INSERT INTO files ...`)
        // ^^ Creating a new prepared statement for EACH file!
        if err != nil {
            return fmt.Errorf("failed to prepare statement: %w", err)
        }
        // stmt.Close() never called!

        _, err = stmt.ExecContext(ctx, ...)
        // ...
    }

    return tx.Commit()
}
```

---

## Transaction Issues (version.go)

```go
func (s *Service) RestoreVersion(ctx context.Context, fileID uuid.UUID, version int, userID uuid.UUID) (*models.FileVersion, error) {
    tx, err := s.db.BeginTx(ctx, nil)
    // ...

    var maxVersion int
    // BUG: Using s.db instead of tx!
    err = s.db.QueryRowContext(ctx,
        "SELECT COALESCE(MAX(version), 0) FROM file_versions WHERE file_id = $1",
        fileID,
    ).Scan(&maxVersion)
    // This query runs OUTSIDE the transaction!
    // ...
}
```

---

## Impact Summary

- **Affected Users**: All users during peak hours
- **Failed Requests**: ~892 in last 5 minutes
- **Degraded Latency**: Average request time increased from 200ms to 12s
- **User Reports**: "Files not loading", "Timeouts", "500 errors"

---

## Root Causes (Suspected)

1. **Connection leak in GetByUserID**: `rows.Close()` not called on error paths
2. **Connection leak in GetVersions**: Loop continues on error instead of returning
3. **Prepared statement leak**: `BulkCreate` creates statements in loop without closing
4. **Transaction isolation bug**: Queries running outside transaction in `RestoreVersion`
5. **Missing error checks**: `rows.Err()` not checked after iteration

---

## Recommended Actions

1. **Immediate**: Restart application pods to release stuck connections
2. **Short-term**: Add `defer rows.Close()` immediately after `Query*` calls
3. **Short-term**: Fix prepared statement leaks with proper `defer stmt.Close()`
4. **Medium-term**: Add connection pool monitoring and alerting
5. **Long-term**: Code review for proper resource cleanup patterns

---

## Files to Investigate

- `internal/repository/file_repo.go`
- `internal/services/versioning/version.go`

---

**Status**: Active
**On-Call**: @sre.kim
**Escalation**: Platform Engineering team notified
