# Production Incident: Intermittent Panics and Data Corruption

## Grafana Alert + PagerDuty Incident

**Alert Name**: VaultFS Error Rate Spike
**Severity**: High (P2)
**First Triggered**: 2024-02-15 16:22 UTC
**Resolved**: Ongoing
**On-Call**: @sre.alex

---

## Alert Configuration

```yaml
alert: VaultFSHighErrorRate
expr: rate(vaultfs_http_errors_total[5m]) > 0.05
for: 3m
labels:
  severity: high
annotations:
  summary: "VaultFS error rate above 5%"
  description: "Current error rate: {{ $value | humanizePercentage }}"
```

## Current Metrics

| Metric | Value | Normal |
|--------|-------|--------|
| Error Rate (5m) | 8.7% | <0.1% |
| Panic Count (1h) | 47 | 0 |
| 500 Responses (1h) | 1,247 | <10 |
| Successful Uploads | 91.3% | 99.9% |

---

## Error Log Patterns

### Pattern 1: Use After Move in File Processing

```
2024-02-15T16:23:45Z ERROR Request failed error="value used after move"
thread 'tokio-runtime-worker' panicked at src/services/storage.rs:89:
borrow of moved value: `file_data`
```

**Frequency**: ~15/hour

### Pattern 2: Double Mutable Borrow

```
2024-02-15T16:25:12Z ERROR Request failed error="already borrowed: BorrowMutError"
thread 'tokio-runtime-worker' panicked at src/services/versioning.rs:156:
already borrowed: BorrowMutError
```

**Frequency**: ~8/hour

### Pattern 3: Partial Move Out of Struct

```
2024-02-15T16:28:33Z ERROR Request failed error="use of partially moved value"
thread 'tokio-runtime-worker' panicked at src/models/file.rs:45:
use of partially moved value: `file_metadata`
```

**Frequency**: ~5/hour

### Pattern 4: Value Moved in Loop

```
2024-02-15T16:31:02Z ERROR Batch operation failed
thread 'tokio-runtime-worker' panicked at src/handlers/files.rs:203:
use of moved value: `processor`
note: value moved in previous iteration of loop
```

**Frequency**: ~10/hour (batch operations only)

---

## Extended Stack Traces

### Trace 1 (storage.rs:89)

```
thread 'tokio-runtime-worker' panicked at 'borrow of moved value: `file_data`':
   0: vaultfs::services::storage::StorageService::process_upload
             at ./src/services/storage.rs:89
   1: vaultfs::handlers::upload::handle_upload::{{closure}}
             at ./src/handlers/upload.rs:67
   2: <core::future::from_generator::GenFuture<T> as core::future::future::Future>::poll
```

### Trace 2 (versioning.rs:156)

```
thread 'tokio-runtime-worker' panicked at 'already borrowed: BorrowMutError':
   0: core::cell::RefCell<T>::borrow_mut
   1: vaultfs::services::versioning::VersionManager::create_version
             at ./src/services/versioning.rs:156
   2: vaultfs::services::versioning::VersionManager::update_file
             at ./src/services/versioning.rs:142
```

---

## User Impact Reports

### Support Ticket #82390

> When I upload a file, sometimes I get "Internal Server Error" and the file doesn't appear in my folder. But when I try to upload again with the same name, it says the file already exists. So the upload partially succeeded?

### Support Ticket #82412

> File versions are getting corrupted. I restored version 3 of my document but got version 1's content. The version numbers in the UI are also wrong after this.

### Support Ticket #82445

> Batch file operations keep failing. I'm trying to move 50 files and only the first 10-15 get moved before I get an error.

---

## Internal Slack Thread

**#backend-eng** - February 15, 2024

**@dev.jordan** (16:45):
> Seeing a lot of borrow checker violations hitting production. These should have been caught at compile time - how are they even possible?

**@dev.emma** (16:52):
> They're runtime panics, not compile errors. We're using `RefCell` for interior mutability in some places. The borrow rules are enforced at runtime, and violations cause panics instead of compile errors.

**@dev.jordan** (16:58):
> Found the storage.rs issue. Line 89:
```rust
let data = self.read_file(&path)?;
self.process(data);  // Moves data
self.validate(data); // ERROR: data already moved!
```

**@dev.emma** (17:05):
> The versioning.rs issue is different. We have:
```rust
let mut versions = self.versions.borrow_mut();
// ... do stuff ...
self.update_metadata(); // This also calls borrow_mut() internally!
```

Nested mutable borrows on the same RefCell.

**@dev.jordan** (17:10):
> And the loop issue in files.rs - we're passing ownership of a processor into a loop:
```rust
for file in files {
    processor.handle(file); // processor moved here
} // Next iteration: processor already moved!
```

**@dev.emma** (17:15):
> The partial move in models/file.rs is interesting:
```rust
let name = file_meta.name; // Moves name field out
println!("{:?}", file_meta); // ERROR: file_meta partially moved
```

**@dev.jordan** (17:20):
> We need to audit all RefCell usage and ownership patterns. These are Rust 101 mistakes but they're causing real production issues.

---

## Sync Service Additional Errors

```
2024-02-15T17:02:33Z ERROR Sync failed for user_abc123
thread 'tokio-runtime-worker' panicked at src/services/sync.rs:234:
borrowed value does not live long enough

2024-02-15T17:05:45Z ERROR Cache lookup failed
  error: "cannot return reference to local variable `result`"
  location: src/services/cache.rs:78
```

These appear related to lifetime issues rather than ownership, but may share similar root causes.

---

## Affected Operations

| Operation | Failure Rate | Impact |
|-----------|-------------|--------|
| Single File Upload | 3.2% | Files partially created |
| Batch File Move | 12.5% | Partial batch completion |
| Version Restore | 8.7% | Wrong version restored |
| File Sync | 5.1% | Sync state corruption |

---

## Questions for Investigation

1. Why are ownership rules being violated at runtime (RefCell panics)?
2. Where is the "use after move" occurring in storage processing?
3. Why are we getting nested mutable borrows in versioning?
4. How is the loop consuming the processor on each iteration?
5. Why is file_meta being partially moved instead of borrowed?

---

## Files to Investigate

Based on error locations:
- `src/services/storage.rs` - Use after move (line 89)
- `src/services/versioning.rs` - Double mutable borrow (line 156)
- `src/services/sync.rs` - Lifetime issue (line 234)
- `src/handlers/files.rs` - Move in loop (line 203)
- `src/models/file.rs` - Partial move (line 45)
- `src/services/cache.rs` - Reference to local variable (line 78)

---

**Status**: INVESTIGATING
**Assigned**: @dev.jordan, @dev.emma
**Follow-up**: Daily standup until resolved
