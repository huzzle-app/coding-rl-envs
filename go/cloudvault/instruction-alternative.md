# CloudVault - Alternative Tasks

## Overview

CloudVault supports 5 alternative task types that test different software engineering skills: implementing new features with cross-service integration, refactoring critical infrastructure, optimizing for performance at scale, extending APIs with advanced functionality, and migrating to distributed architectures. Each task uses the existing codebase while exercising different aspects of system design and engineering.

## Environment

- **Language**: Go 1.21
- **Infrastructure**: Gin, PostgreSQL, Redis, MinIO (S3-compatible object storage)
- **Difficulty**: Senior
- **Setup**: `docker compose up -d` to start services; `go test -race -v ./...` to run tests

## Tasks

### Task 1: Implement Folder Sharing with Recursive Permissions (Feature Development)

Enterprise customers require the ability to share entire folders with granular permission inheritance. Folders and their contents (files and subfolders) should automatically inherit share permissions, with the ability to override permissions at any level. The implementation must handle deep hierarchies efficiently and integrate with the sync service to notify clients of permission changes in real-time.

**Acceptance Criteria**: Folders can be shared via `/api/shares` with `is_directory: true`, child items inherit parent permissions with override support, deep hierarchies (100+ levels) complete permission checks in under 100ms, permission changes propagate to sync service, all existing tests pass.

### Task 2: Refactor Storage Service for Multi-Backend Support (Refactoring)

The storage service is currently tightly coupled to MinIO/S3. Business requirements demand support for Azure Blob Storage, Google Cloud Storage, and local filesystem storage for on-premise deployments. Introduce a `StorageBackend` interface that encapsulates all operations (Upload, Download, Delete, ListObjects, GetMetadata), with each backend independently configurable and testable while preserving backward compatibility.

**Acceptance Criteria**: New `StorageBackend` interface defined with all required operations, MinIO implementation extracted into separate backend module, backend selection via `STORAGE_BACKEND` environment variable, chunked uploads work across all backends, all existing tests pass, context cancellation supported, memory usage constant regardless of file size.

### Task 3: Optimize Sync Service for Large File Collections (Performance Optimization)

Enterprise users with 100,000+ files are experiencing sync performance issues. Initial sync takes over 5 minutes and change detection causes noticeable latency. Optimize the sync service with cursor-based pagination for change feeds, batch processing, and efficient delta computation. Implement memory-bounded caching and automatic cleanup of stale sync states.

**Acceptance Criteria**: Initial sync for 100,000 files completes in under 30 seconds, incremental sync with 1,000 changes in under 2 seconds, memory usage stays under 50MB per user, cursor-based pagination with configurable batch sizes, automatic cleanup of stale states, concurrent syncs don't cause data races, existing tests pass with improved performance.

### Task 4: Extend Versioning API with Diff and Rollback Features (API Extension)

The versioning system only supports listing and restoring versions. Users need advanced features: viewing diffs between versions, bulk rollback of multiple files to a specific timestamp, and version comparison with conflict detection. Add endpoints for comparing versions and point-in-time folder restore, with integration to the conflict resolution system.

**Acceptance Criteria**: New `GET /api/files/:id/versions/:v1/diff/:v2` endpoint returns version differences (metadata and optional content diff), new `POST /api/folders/:id/restore` endpoint supports point-in-time folder restore, conflict detection for pending sync changes, bulk rollback is atomic within transactions, API documentation updated, existing tests pass.

### Task 5: Migrate Rate Limiter to Distributed Architecture (Migration)

The current rate limiter uses in-memory token buckets, which fails in multi-instance deployments behind a load balancer. Each instance maintains separate rate limit state, allowing users to exceed limits by targeting different instances. Migrate to Redis-backed distributed rate limiting with sliding window algorithm, supporting per-IP and per-user limits with feature flag for gradual rollout and graceful Redis failure handling.

**Acceptance Criteria**: Rate limit state stored in Redis using sliding window algorithm, consistent rate limiting across multiple instances, per-IP and per-user limits configurable independently, different limits per API endpoint group, feature flag `RATE_LIMIT_DISTRIBUTED=true` enables Redis-backed limiting, graceful degradation to in-memory when Redis unavailable, proper connection pool management, existing tests pass in both modes.

## Getting Started

Start Docker services and run tests:

```bash
docker compose up -d
go test -race -v ./...
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
