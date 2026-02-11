# CloudVault - Alternative Task Specifications

These alternative tasks provide different entry points into the CloudVault codebase, each focusing on a specific aspect of cloud storage platform development.

---

## Task 1: Implement Folder Sharing with Recursive Permissions (Feature Development)

### Description

CloudVault currently supports sharing individual files, but enterprise customers have requested the ability to share entire folders with granular permission inheritance. When a folder is shared, all files and subfolders within it should automatically inherit the share permissions, with the ability to override permissions at any level.

The implementation must handle the complexity of recursive permission propagation, including scenarios where a subfolder already has explicit permissions that should take precedence over inherited ones. The system must also efficiently handle deep folder hierarchies (up to 100 levels) without performance degradation, and properly revoke inherited permissions when the parent share is deleted.

Additionally, the sharing system must integrate with the existing sync service to notify connected clients when folder permissions change, allowing real-time updates to file availability across devices.

### Acceptance Criteria

- Folders can be shared via the existing `/api/shares` endpoint by setting `is_directory: true`
- Child files and folders inherit parent share permissions by default
- Explicit permissions on child items override inherited permissions
- Deleting a parent share revokes all inherited permissions recursively
- Permission changes propagate to the sync service for real-time client updates
- Deep folder hierarchies (100+ levels) complete permission checks in under 100ms
- Share tokens remain valid for nested content access
- All existing file sharing tests continue to pass

### Test Command

```bash
go test -race -v ./...
```

---

## Task 2: Refactor Storage Service for Multi-Backend Support (Refactoring)

### Description

The current storage service is tightly coupled to MinIO/S3-compatible storage. The business requires support for multiple storage backends including Azure Blob Storage, Google Cloud Storage, and local filesystem storage for on-premise deployments. The storage service must be refactored to use a clean abstraction layer.

The refactoring should introduce a `StorageBackend` interface that encapsulates all storage operations (Upload, Download, Delete, ListObjects, GetMetadata). Each backend implementation should be independently configurable and testable. The chunked upload functionality must work consistently across all backends, handling the different multipart upload semantics of each provider.

The refactoring must preserve backward compatibility with existing code that uses the storage service, ensuring all current tests pass without modification. Configuration should allow runtime selection of the storage backend via environment variables.

### Acceptance Criteria

- New `StorageBackend` interface defined with all required operations
- MinIO implementation extracted into a separate backend module
- Backend selection configurable via `STORAGE_BACKEND` environment variable
- Chunked uploads work correctly with the abstracted interface
- All existing storage tests pass without modification
- New interface supports context cancellation and timeout propagation
- Backend implementations are independently unit testable with mock dependencies
- Memory usage remains constant regardless of file size during streaming operations

### Test Command

```bash
go test -race -v ./...
```

---

## Task 3: Optimize Sync Service for Large File Collections (Performance Optimization)

### Description

Enterprise customers with 100,000+ files per user are experiencing sync performance issues. The initial sync takes over 5 minutes, and change detection during incremental syncs causes noticeable latency. The sync service must be optimized to handle large file collections efficiently.

The current implementation fetches all changes since the last sync timestamp and processes them sequentially. This approach doesn't scale well when users have extensive file histories. The optimization should implement cursor-based pagination for change feeds, batch processing for change application, and efficient delta computation using Merkle trees or similar structures.

Additionally, the sync state management has memory growth issues when many devices are connected. The optimization must include efficient cleanup of stale sync states and implement memory-bounded caching for frequently accessed sync data.

### Acceptance Criteria

- Initial sync for 100,000 files completes in under 30 seconds
- Incremental sync with 1,000 changes completes in under 2 seconds
- Memory usage for sync state stays under 50MB per user regardless of file count
- Change feed supports cursor-based pagination with configurable batch sizes
- Stale sync states (no activity for 30 days) are automatically cleaned up
- Concurrent sync operations from multiple devices don't cause data races
- All existing sync tests pass with improved performance
- New benchmarks demonstrate performance improvements

### Test Command

```bash
go test -race -v ./...
```

---

## Task 4: Extend Versioning API with Diff and Rollback Features (API Extension)

### Description

The current versioning system only supports listing versions and restoring to a specific version. Users have requested advanced features including: viewing diffs between versions, bulk rollback of multiple files to a specific point in time, and version comparison with conflict detection for files modified on multiple devices.

The API extension should add endpoints for comparing any two versions of a file, showing metadata changes (size, checksum, modified date) and optionally content diffs for text files. A new "point-in-time restore" feature should allow users to rollback an entire folder to how it appeared at a specific timestamp.

The extension must integrate with the existing conflict resolution system in the sync service, detecting when a version rollback would conflict with pending changes on other devices and providing appropriate resolution options.

### Acceptance Criteria

- New `GET /api/files/:id/versions/:v1/diff/:v2` endpoint returns version differences
- Diff response includes metadata changes and optional content diff for text files
- New `POST /api/folders/:id/restore` endpoint supports point-in-time folder restore
- Point-in-time restore creates new versions rather than deleting history
- Conflict detection warns when rollback conflicts with pending sync changes
- Bulk rollback operations are atomic (all-or-nothing within a transaction)
- API documentation updated with new endpoint specifications
- All existing versioning tests continue to pass

### Test Command

```bash
go test -race -v ./...
```

---

## Task 5: Migrate Rate Limiter to Distributed Architecture (Migration)

### Description

The current rate limiter uses in-memory token buckets, which doesn't work correctly in a multi-instance deployment. When CloudVault is deployed behind a load balancer with multiple instances, each instance maintains its own rate limit state, allowing users to exceed limits by having requests routed to different instances.

The rate limiter must be migrated to use Redis as a distributed state store, ensuring consistent rate limiting across all instances. The migration should implement the sliding window algorithm using Redis sorted sets for accurate rate tracking, and support both per-IP and per-user rate limiting with configurable limits for different API endpoints.

The migration must be backward compatible, with a feature flag to switch between in-memory and distributed modes. The distributed implementation must handle Redis connection failures gracefully, falling back to a degraded mode that still provides some protection against abuse.

### Acceptance Criteria

- Rate limit state stored in Redis using sliding window algorithm
- Consistent rate limiting across multiple CloudVault instances
- Per-IP and per-user rate limits configurable independently
- Different rate limits configurable per API endpoint group
- Feature flag `RATE_LIMIT_DISTRIBUTED=true` enables Redis-backed limiting
- Graceful degradation to in-memory limiting when Redis is unavailable
- Redis connection pool properly managed with configurable pool size
- All existing rate limit tests pass in both modes
- New integration tests verify distributed behavior across instances

### Test Command

```bash
go test -race -v ./...
```
