# Observability Alert: Memory Growth and Resource Exhaustion

## DataDog Anomaly Detection

**Alert Name**: VaultFS Memory Anomaly Detected
**Severity**: Warning -> Critical (Escalated)
**First Detected**: 2024-02-14 08:00 UTC
**Escalated to Critical**: 2024-02-17 14:30 UTC
**Team**: Platform SRE

---

## Anomaly Detection Details

```
Metric: vaultfs.memory.heap_bytes
Baseline: 512MB - 768MB
Current: 3.2GB (4.2x baseline)
Trend: +180MB/hour (linear growth)
Forecast: OOM in ~6 hours at current rate
```

## Memory Profile Over Time

```
Day 1 (Feb 14):
  08:00  512MB (baseline after restart)
  12:00  1.1GB
  18:00  1.8GB
  23:00  2.4GB

Day 2 (Feb 15):
  08:00  768MB (restarted overnight)
  14:00  1.5GB
  20:00  2.1GB

Day 3 (Feb 16):
  08:00  640MB (restarted overnight)
  16:00  2.0GB

Day 4 (Feb 17):
  08:00  720MB (restarted overnight)
  14:30  3.2GB (ALERT ESCALATED)
```

---

## Resource Metrics Dashboard

| Resource | Current | Limit | Status |
|----------|---------|-------|--------|
| Heap Memory | 3.2GB | 4GB | CRITICAL |
| File Descriptors | 847 | 1024 | WARNING |
| Active Connections | 234 | 500 | OK |
| Temp Files on Disk | 1,247 | - | ABNORMAL |

---

## Memory Profiler Output (heaptrack)

```
Top allocations by cumulative size:

1. 892MB  src/models/folder.rs:34  Folder::new
          -> Rc<RefCell<Folder>> cycles detected
          -> 12,847 unreachable Folder objects

2. 456MB  src/services/sync.rs:178  SyncService::queue_event
          -> unbounded channel growth
          -> 2.3M pending events in channel

3. 234MB  src/storage/chunker.rs:89  ChunkProcessor::process
          -> File handles not closed on error
          -> 847 open file descriptors

4. 178MB  src/models/temp_file.rs:23  TempFile::new
          -> Drop impl panics, preventing cleanup
          -> 1,247 orphaned temp files on disk
```

---

## Error Logs Related to Resource Issues

### Temp File Cleanup Panics

```
2024-02-17T12:45:23Z ERROR TempFile cleanup failed
thread 'tokio-runtime-worker' panicked at 'called `unwrap()` on a `None` value'
    at src/models/temp_file.rs:67

2024-02-17T12:45:23Z WARN  Drop handler panicked, resources may leak
```

### File Descriptor Warnings

```
2024-02-17T13:02:45Z WARN  Approaching file descriptor limit: 847/1024
2024-02-17T13:15:12Z ERROR Failed to open file: Too many open files (os error 24)
2024-02-17T13:15:12Z ERROR Chunk processing failed: resource temporarily unavailable
```

### Sync Queue Backpressure

```
2024-02-17T14:00:00Z WARN  Sync event queue size: 1,500,000
2024-02-17T14:15:00Z WARN  Sync event queue size: 1,800,000
2024-02-17T14:30:00Z WARN  Sync event queue size: 2,300,000
2024-02-17T14:30:01Z WARN  Memory pressure detected, GC struggling
```

---

## Internal Slack Thread

**#sre-incidents** - February 17, 2024

**@sre.kim** (14:35):
> VaultFS memory alert escalated to critical. We're at 3.2GB and climbing. Restarting buys us ~8 hours before it happens again.

**@dev.marcus** (14:42):
> heaptrack shows the top leak is in folder.rs. Let me check...

**@dev.marcus** (14:48):
> Found it. We have parent-child folder relationships using `Rc<RefCell<Folder>>`. Each folder holds an Rc to its parent, and the parent holds Rcs to its children. Classic reference cycle - Rust's Rc doesn't handle cycles.

**@dev.sarah** (14:55):
> The sync queue is also growing unbounded. We're using `tokio::sync::mpsc::unbounded_channel()` and the consumer can't keep up with producers during peak load. Queue just keeps growing.

**@dev.marcus** (15:02):
> The file descriptor leak is in chunker.rs. When chunk processing fails partway through, we return early but don't close the file handle:
```rust
fn process(&self, path: &Path) -> Result<Vec<Chunk>> {
    let file = File::open(path)?;
    // ... processing ...
    if validation_failed {
        return Err(Error::ValidationFailed); // file not closed!
    }
    // ... more processing ...
}
```

**@dev.sarah** (15:08):
> And the temp file issue - the Drop impl panics because it unwraps an Option that can be None:
```rust
impl Drop for TempFile {
    fn drop(&mut self) {
        let path = self.path.take().unwrap(); // Panics if already taken!
        std::fs::remove_file(path).unwrap();  // Also panics on error!
    }
}
```

When Drop panics, the temp file never gets deleted.

**@sre.kim** (15:15):
> So we have four separate leak sources:
> 1. Rc cycle in folder hierarchy
> 2. Unbounded channel in sync service
> 3. Unclosed files on error paths
> 4. Panicking Drop impl for temp files

**@dev.marcus** (15:20):
> Correct. All four need fixes. For now, we need to restart every 6-8 hours to stay ahead of OOM.

---

## Customer Impact

### Support Ticket #82498

> My folder structure is really deep (20+ levels) and after working for a few hours, the web interface becomes super slow. Logging out and back in doesn't help, only waiting until tomorrow works.

### Support Ticket #82512

> Sync has been "pending" for 3 hours now. The sync icon just spins forever. My files on mobile are days out of date.

### Support Ticket #82534

> I get "upload failed" errors randomly. The error message says something about "too many open files" which doesn't make sense since I'm only uploading one file.

---

## Temporary Mitigations in Place

1. Kubernetes HPA scaled pods from 3 to 8 to distribute load
2. Pod restart scheduled every 6 hours via CronJob
3. Sync queue consumer scaled from 1 to 4 workers
4. File descriptor ulimit increased from 1024 to 4096

---

## Questions for Investigation

1. How do we break the Rc cycle in folder parent/child relationships?
2. Should the sync channel be bounded with backpressure?
3. Why aren't file handles being closed on error paths?
4. Why does the TempFile Drop impl panic instead of handling errors gracefully?

---

## Files to Investigate

Based on profiler output:
- `src/models/folder.rs` - Rc reference cycles (line 34)
- `src/services/sync.rs` - Unbounded channel growth (line 178)
- `src/storage/chunker.rs` - File handle leaks (line 89)
- `src/models/temp_file.rs` - Panicking Drop implementation (line 67)

---

## Estimated Impact if Unresolved

- OOM crashes every 6-8 hours
- Sync delays of 3+ hours during peak
- Random upload failures under load
- Disk space consumption from orphaned temp files

---

**Status**: ACTIVE
**Assigned**: @dev.marcus, @dev.sarah
**Workaround**: Scheduled restarts every 6 hours
**Target Resolution**: February 19, 2024
