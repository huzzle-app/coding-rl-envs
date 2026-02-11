# VaultFS - Alternative Tasks

This document contains alternative task specifications for the VaultFS distributed file storage platform. Each task represents a realistic engineering challenge in the file storage domain.

---

## Task 1: Incremental Sync Protocol (Feature Development)

### Description

VaultFS currently uses a full-file synchronization model where any change to a file requires retransmitting the entire file to connected clients. This approach becomes prohibitively expensive for large files where users make small edits, such as appending log data or modifying document metadata.

Implement an incremental sync protocol that detects and transmits only the changed portions of files. The system should compute delta differences between file versions, efficiently encode these deltas, and apply them on the client side to reconstruct the updated file. The protocol must handle concurrent modifications gracefully and maintain data integrity through checksums.

The implementation should integrate with the existing versioning service to track which deltas apply between specific version pairs, enabling clients to sync from any previous version to the current state through a chain of deltas or a direct full-file fallback when the delta chain becomes too long.

### Acceptance Criteria

- Delta computation correctly identifies changed byte ranges between two file versions
- Deltas are transmitted only when they would be smaller than retransmitting the full file
- Client-side delta application reconstructs files with byte-perfect accuracy
- Checksum validation ensures delta integrity before and after application
- Concurrent delta generation for the same file produces consistent results
- Delta chains exceeding a configurable depth trigger automatic full-file sync fallback
- All existing sync tests continue to pass
- New tests verify delta correctness for files of varying sizes (1KB to 1GB)

### Test Command

```bash
cargo test
```

---

## Task 2: Lock Manager Hierarchical Refactoring (Refactoring)

### Description

The current lock manager implementation uses flat, independent locks for files and users, requiring callers to manually coordinate lock acquisition order to prevent deadlocks. This design has led to subtle concurrency bugs and makes it difficult to implement new features like folder-level locking or cross-user collaborative editing.

Refactor the lock manager to use a hierarchical locking model where locks form a tree structure: user locks contain folder locks, which contain file locks. Acquiring a parent lock should implicitly protect all children, while acquiring a child lock should only block operations on that specific resource. The refactored design must support lock upgrades (read to write) and downgrades without releasing the lock.

The new architecture should expose a clean API that makes deadlock-free usage the natural path, eliminating the need for callers to understand lock ordering internals. All existing lock functionality must be preserved while enabling future extensions like range locks within files.

### Acceptance Criteria

- Hierarchical lock tree correctly models user -> folder -> file relationships
- Parent lock acquisition blocks conflicting child lock requests
- Child lock acquisition does not block sibling or unrelated locks
- Lock upgrade from read to write succeeds when no other readers hold the lock
- Lock downgrade from write to read always succeeds immediately
- Deadlock detection identifies and reports circular wait conditions
- Existing lock_file_for_user and lock_user_files APIs remain backward compatible
- All concurrency tests pass under high contention scenarios

### Test Command

```bash
cargo test
```

---

## Task 3: Chunked Upload Memory Optimization (Performance Optimization)

### Description

The storage service currently loads entire files into memory before splitting them into chunks for upload to the object store. For large files (multiple gigabytes), this causes significant memory pressure, leading to out-of-memory errors on resource-constrained deployments and degraded performance under concurrent upload load.

Optimize the chunked upload pipeline to use streaming processing where file data flows through the system in fixed-size buffers without materializing the complete file in memory. The implementation should pipeline chunk hashing, compression, and upload operations so that multiple chunks can be in flight simultaneously while maintaining strict memory bounds.

The optimization must preserve the existing hash computation (which currently requires seeing all file bytes) by implementing an incremental hashing strategy that computes the final file hash as chunks stream through. Upload progress tracking and resumable upload support must continue to function correctly.

### Acceptance Criteria

- Peak memory usage during upload remains bounded regardless of file size
- Streaming upload of 10GB file uses less than 256MB of heap memory
- Incremental hash computation produces identical results to full-file hashing
- Chunk upload pipelining achieves at least 80% of theoretical network throughput
- Upload progress callbacks fire accurately as chunks complete
- Resumable uploads correctly identify and skip already-uploaded chunks
- No regression in upload latency for small files (under 10MB)
- Storage tests pass with memory limits enforced via test harness

### Test Command

```bash
cargo test
```

---

## Task 4: Batch File Operations API (API Extension)

### Description

The current VaultFS API supports operations on individual files only, requiring clients to make separate requests for each file in multi-file workflows. This creates excessive network round trips and prevents atomic operations across file sets, such as moving an entire folder or applying consistent permissions to multiple files.

Extend the API with batch operation endpoints that accept lists of files and execute operations atomically. Batch operations should support mixed operation types within a single request (e.g., move some files while deleting others), with clear semantics for partial failures. The API must provide detailed per-file status in responses while maintaining overall request atomicity where possible.

The batch API should integrate with the existing lock manager to acquire all necessary locks before beginning operations, preventing inconsistent states from concurrent requests. Rate limiting and request size limits must prevent abuse while allowing legitimate large-batch use cases.

### Acceptance Criteria

- Batch endpoint accepts up to 1000 file operations in a single request
- Mixed operation types (move, copy, delete, update metadata) work within one batch
- All-or-nothing atomicity mode rolls back partial changes on any failure
- Best-effort mode continues after failures and reports per-file status
- Lock acquisition for batch operations prevents deadlocks with concurrent requests
- Batch operations are more efficient than equivalent individual requests (measured latency)
- Request size limits prevent memory exhaustion from oversized batches
- API documentation accurately describes batch semantics and error handling

### Test Command

```bash
cargo test
```

---

## Task 5: Storage Backend Migration Framework (Migration)

### Description

VaultFS currently hardcodes MinIO/S3 as its object storage backend. Enterprise customers have requested support for alternative storage backends including Azure Blob Storage, Google Cloud Storage, and on-premises solutions like Ceph. Adding each backend as a one-off integration creates maintenance burden and inconsistent behavior across deployments.

Implement a storage backend abstraction layer that decouples VaultFS core logic from specific storage implementations. The framework should define a trait (interface) that all backends must implement, covering file upload, download, delete, listing, and metadata operations. Include a migration system that can copy data between backends with progress tracking and verification.

The migration framework must support online migration where the system remains available during the transfer, reading from the old backend while writing new data to the new backend, then switching over once migration completes. Rollback capabilities should allow reverting to the previous backend if issues arise.

### Acceptance Criteria

- Storage backend trait defines all operations needed by VaultFS services
- MinIO/S3 backend implements the trait with current functionality preserved
- At least one additional backend (Azure Blob or GCS) demonstrates trait flexibility
- Migration system copies data between backends with integrity verification
- Online migration serves reads from source while writing to destination
- Migration progress is observable through logs and optional metrics
- Cutover to new backend is atomic from client perspective
- Rollback restores service using previous backend within defined SLA
- All storage tests pass against each implemented backend

### Test Command

```bash
cargo test
```
