# Incident Report: Memory Leak in Production

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-15 03:42 UTC
**Acknowledged**: 2024-01-15 03:45 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: cloudvault-api-prod-1 memory usage at 94%
Host: cloudvault-api-prod-1.us-east-1.internal
Metric: container_memory_usage_bytes
Threshold: >90% for 5 minutes
Current Value: 94.2%
```

## Timeline

**03:42 UTC** - Initial alert fired for pod memory exceeding 90%

**03:48 UTC** - Second pod (cloudvault-api-prod-2) also breaching threshold

**03:55 UTC** - First pod OOM-killed by Kubernetes
```
reason: OOMKilled
exitCode: 137
restartCount: 1
```

**04:02 UTC** - Pod restarted, memory immediately starts climbing again

**04:15 UTC** - Memory back at 75% after just 13 minutes of uptime

## Grafana Dashboard Observations

### Memory Profile
- Memory grows linearly regardless of request volume
- No correlation with file upload sizes
- Pattern persists even during low-traffic periods (2-4 AM)
- Rate: approximately +50MB every 10 minutes

### Goroutine Count
```
Metric: go_goroutines
Time: 03:00 - 04:00 UTC

03:00  1,247 goroutines
03:15  1,892 goroutines
03:30  2,543 goroutines
03:45  3,201 goroutines
04:00  3,847 goroutines (after restart: 412)
```

### Active Operations
- File uploads: ~120/min
- Chunked uploads initiated: ~45/min
- Chunked uploads completed: ~42/min (3 abandoned per minute average)
- Sync operations started: ~200/min
- Sync watchers active: fluctuating between 50-300

## Customer Impact

- Users reported "upload stuck at 100%" - progress never completes
- File sync showing stale data
- Sporadic 502 errors during pod restarts

## Stack Traces from pprof

Memory allocation hotspots (sampled during incident):

```
    87.5MB  internal/services/storage.(*Service).Upload
            at /app/internal/services/storage/storage.go:67

    42.3MB  internal/services/sync.(*Service).WatchChanges
            at /app/internal/services/sync/sync.go:214

    28.7MB  internal/middleware.(*RateLimiter).StartCleanup
            at /app/internal/middleware/ratelimit.go:102
```

Goroutine dump excerpt:
```
goroutine 15847 [chan receive]:
internal/services/storage.(*Service).Upload.func1()
    /app/internal/services/storage/storage.go:69 +0x3f
created by internal/services/storage.(*Service).Upload
    /app/internal/services/storage/storage.go:67 +0x142

goroutine 15892 [select]:
internal/services/sync.(*Service).WatchChanges.func1()
    /app/internal/services/sync/sync.go:218 +0x1a7
created by internal/services/sync.(*Service).WatchChanges
    /app/internal/services/sync/sync.go:213 +0x9c
```

## Attempted Mitigations

1. Increased pod memory limit from 2Gi to 4Gi - just delayed the OOM
2. Horizontal scaling to 5 pods - all eventually hit memory limit
3. Restarting pods provides temporary relief (~20 minutes before issues return)

## Questions for Investigation

1. Why are goroutine counts growing unbounded?
2. What is creating these long-running goroutines in storage/sync services?
3. Why aren't goroutines being cleaned up when operations complete?
4. Is there a missing cancellation or cleanup mechanism?

## Relevant Logs

```
2024-01-15T03:42:18Z INFO  Upload started session=a1b2c3d4
2024-01-15T03:42:19Z INFO  Upload progress: 1048576 bytes
2024-01-15T03:42:20Z INFO  Upload progress: 2097152 bytes
2024-01-15T03:42:21Z INFO  Upload complete session=a1b2c3d4
# Note: "Upload progress" logs continue appearing for this session
# even after "Upload complete" - this seems wrong
2024-01-15T03:42:25Z INFO  Upload progress: 3145728 bytes
2024-01-15T03:42:30Z INFO  Upload progress: 4194304 bytes
...
```

## Files to Investigate

Based on stack traces, focus on:
- `internal/services/storage/storage.go`
- `internal/services/sync/sync.go`
- `internal/middleware/ratelimit.go`

---

**Status**: INVESTIGATING
**Assigned**: @platform-team
**Follow-up**: Post-incident review scheduled for 2024-01-16 10:00 UTC
