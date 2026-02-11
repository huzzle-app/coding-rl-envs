# VaultFS - Alternative Tasks

## Overview

VaultFS supports five alternative engineering tasks beyond the core debugging challenge. These tasks involve extending the filesystem service with new capabilities including incremental sync, hierarchical locking, memory optimization, batch operations, and backend flexibility.

## Environment

- **Language**: Rust
- **Infrastructure**: PostgreSQL (database), Redis (cache), MinIO/S3 (object storage), Axum (web framework), Tokio (async runtime)
- **Difficulty**: Senior (2-4h per task)

## Tasks

### Task 1: Incremental Sync Protocol (Feature Development)

Implement delta-based synchronization that detects and transmits only changed portions of files. The system computes diffs between versions, efficiently encodes deltas, and applies them on the client side. Integration with the versioning service enables clients to sync through delta chains with automatic full-file fallback when efficient.

**Acceptance Criteria**: Delta computation correct for all file types, deltas smaller than full retransmission, byte-perfect client reconstruction, checksum validation, concurrent delta safety, configurable delta chain depth, all existing tests pass, comprehensive coverage for files 1KB-1GB.

### Task 2: Lock Manager Hierarchical Refactoring (Refactoring)

Refactor the lock manager from flat independent locks to a hierarchical tree structure where user locks contain folder locks, which contain file locks. Parent lock acquisition implicitly protects children while maintaining deadlock-free semantics. Support lock upgrades (read to write) and downgrades without releasing, exposing a clean API that makes correct usage natural.

**Acceptance Criteria**: Hierarchical tree models user → folder → file correctly, parent locks block conflicting children, child locks don't block siblings, read-to-write upgrades work when no other readers, write-to-read downgrade always succeeds, deadlock detection works, backward-compatible with existing APIs, high-contention concurrency tests pass.

### Task 3: Chunked Upload Memory Optimization (Performance Optimization)

Optimize upload pipeline from materializing full files in memory to streaming fixed-size buffers. Pipeline chunk hashing, compression, and uploads simultaneously while maintaining strict memory bounds. Implement incremental hashing (computing final hash as chunks stream) and preserve resumable uploads and progress tracking without regression on small files.

**Acceptance Criteria**: Peak memory bounded regardless of file size, 10GB file upload uses <256MB heap, incremental hash matches full-file hashing, chunk pipelining achieves 80%+ network throughput, progress callbacks accurate, resumable uploads skip already-uploaded chunks, no small-file latency regression, tests pass with memory limits enforced.

### Task 4: Batch File Operations API (API Extension)

Extend the API with batch endpoints accepting lists of files and executing operations atomically. Support mixed operation types (move, copy, delete, update metadata) with clear partial-failure semantics. Batch API integrates with lock manager to acquire all locks before operations, preventing inconsistent states from concurrent requests. Include rate limiting and request size controls.

**Acceptance Criteria**: Batch endpoint accepts up to 1000 operations, mixed types work in one request, all-or-nothing atomicity mode rolls back on failure, best-effort mode continues and reports per-file status, lock acquisition prevents deadlocks, batch more efficient than individual requests, request size limits prevent exhaustion, API documentation accurate.

### Task 5: Storage Backend Migration Framework (Migration)

Implement a backend abstraction layer decoupling core logic from storage implementations. Define a trait covering file upload, download, delete, listing, and metadata. Include migration system copying data between backends with verification. Support online migration (reading old, writing new, then cutover) with rollback capabilities.

**Acceptance Criteria**: Storage trait defines all needed operations, MinIO/S3 backend implements trait with current functionality, additional backend (Azure Blob/GCS) demonstrates flexibility, migration copies with verification, online migration serves reads from source while writing to destination, cutover atomic from client perspective, rollback restores previous backend within SLA, all storage tests pass.

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run tests
cargo test

# Run task-specific tests
cargo test task_name
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
