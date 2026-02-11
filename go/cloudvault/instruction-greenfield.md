# CloudVault - Greenfield Implementation Tasks

## Overview

CloudVault supports 3 greenfield implementation tasks that require building new modules from scratch using existing codebase patterns and architecture. Each task provides detailed interface contracts and acceptance criteria to guide implementation.

## Environment

- **Language**: Go 1.21
- **Infrastructure**: PostgreSQL, Redis, MinIO (S3-compatible object storage)
- **Difficulty**: Senior
- **Setup**: Study existing patterns in `internal/services/`, `internal/repository/`, `internal/handlers/`, and `internal/models/`

## Prerequisites

- Understand service constructor pattern: `NewService(cfg *config.Config) (*Service, error)`
- Review error handling: `fmt.Errorf("failed to X: %w", err)`
- Study context propagation in database/storage operations
- Examine test patterns in `tests/unit/` and `tests/integration/`

## Tasks

### Task 1: File Deduplication Service (New Service Module)

Implement a content-addressable deduplication service that identifies duplicate files across users and storage. The service uses content hashing to detect duplicates and maintains reference counting for safe deletion. When files with identical content are uploaded, only one copy is stored while reference counts track how many files use that content. When a file is deleted, its reference count decreases, and content is garbage-collected when count reaches zero.

**Interface**: `Service` interface with methods for `CheckDuplicate()`, `Store()`, `Reference()`, `Dereference()`, `GetEntry()`, `GetFileMapping()`, `GetUserDuplicates()`, `GetStats()`, and `RunGarbageCollection()`.

**Key Components**: `DedupEntry` (SHA-256 hash, storage location, size, reference count), `FileMapping` (maps user file to deduplicated content), `DedupStats` (deduplication ratio and space saved).

**Location**: Create `internal/services/dedup/dedup.go`, `internal/services/dedup/store.go`, and `tests/unit/dedup_test.go`.

**Acceptance Criteria**: Unit tests pass (10+ test cases), integrates with `storage.Service` and `repository.FileRepository`, thread-safe reference counting, graceful GC when references reach zero, minimum 80% code coverage.

### Task 2: Thumbnail Generation Service (Async Worker Pattern)

Implement an asynchronous thumbnail generation service for image and document files. The service generates thumbnails of configurable sizes (small 64x64, medium 256x256, large 512x512, custom), caches results in Redis, and handles multiple file formats. Generation can be synchronous for immediate needs or asynchronous via a worker pool for batch processing.

**Interface**: `Service` interface with methods for `Generate()`, `GenerateAsync()`, `GetJobStatus()`, `Get()`, `GetAll()`, `Invalidate()`, `InvalidateAll()`, `GetSupportedFormats()`, `IsSupported()`, and `Warmup()`.

**Key Components**: `Thumbnail` (file ID, size, dimensions, format, storage location), `GenerateOptions` (width/height, format, quality, crop mode), `JobStatus` (job ID, status, progress, error details).

**Location**: Create `internal/services/thumbnail/thumbnail.go`, `internal/services/thumbnail/processor.go`, `internal/services/thumbnail/cache.go`, and `tests/unit/thumbnail_test.go`.

**Acceptance Criteria**: Unit tests pass (18+ test cases), worker pool for async generation with proper shutdown, integrates with `storage.Service` and Redis, handles concurrent generation correctly, supports sync and async modes, minimum 80% code coverage.

### Task 3: File Search Indexer (Full-Text Search with Real-Time Updates)

Implement a full-text search indexer that maintains a searchable index of file metadata and content. The service supports complex queries with filters (by path, extension, MIME type, date range, size), sorting (by relevance, name, date, size), pagination, and real-time faceted results. Search results can be highlighted and suggest corrections for typos.

**Interface**: `Service` interface with methods for `Index()`, `IndexBatch()`, `Delete()`, `DeleteByUser()`, `Search()`, `Suggest()`, `Reindex()`, `GetDocument()`, `UpdateTags()`, `GetStats()`, and `Subscribe()`.

**Key Components**: `Document` (file metadata and extracted text content), `SearchQuery` (full-text query with filters and pagination), `SearchResult` (matching documents with relevance scores, facets, suggestions), `IndexEvent` (real-time index update notifications).

**Location**: Create `internal/services/search/indexer.go`, `internal/services/search/query.go`, `internal/services/search/analyzer.go`, and `tests/unit/search_test.go`.

**Acceptance Criteria**: Unit tests pass (17+ test cases), integrates with `repository.FileRepository` and Redis, supports full-text queries with filters and sorting, real-time subscription for index updates, worker pool for async indexing, minimum 80% code coverage.

## Getting Started

Read existing code structure:

```bash
# Study service patterns
head -50 internal/services/storage/storage.go
head -50 internal/repository/file.go

# Understand configuration
cat internal/config/config.go

# Review test patterns
head -100 tests/unit/auth_test.go
```

Run tests:

```bash
go test -race -v ./...
```

## Success Criteria

Each task implementation meets its acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md), including all unit tests passing and minimum 80% code coverage.
