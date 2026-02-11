# CloudVault - Greenfield Implementation Tasks

These tasks require implementing NEW modules from scratch. Each task builds upon the existing CloudVault architecture and patterns. Study the existing codebase structure before beginning.

## Prerequisites

- Understand existing patterns in `internal/services/`, `internal/repository/`, and `internal/handlers/`
- Review `internal/models/` for model conventions
- Study `internal/config/config.go` for configuration patterns
- Review existing test patterns in `tests/unit/` and `tests/integration/`

## Test Command

```bash
go test -v ./...
```

---

## Task 1: File Deduplication Service

### Overview

Implement a content-addressable deduplication service that identifies duplicate files across users and storage. The service should use content hashing to detect duplicates and maintain reference counting for safe deletion.

### Location

Create new files at:
- `internal/services/dedup/dedup.go`
- `internal/services/dedup/store.go`
- `tests/unit/dedup_test.go`

### Interface Contract

```go
package dedup

import (
    "context"
    "io"

    "github.com/google/uuid"
)

// DedupEntry represents a deduplicated content block
type DedupEntry struct {
    ContentHash  string    `json:"content_hash" db:"content_hash"`   // SHA-256 hash of content
    StorageKey   string    `json:"storage_key" db:"storage_key"`     // Location in object storage
    Size         int64     `json:"size" db:"size"`                   // Size in bytes
    RefCount     int       `json:"ref_count" db:"ref_count"`         // Number of files referencing this content
    CreatedAt    time.Time `json:"created_at" db:"created_at"`
    LastAccessed time.Time `json:"last_accessed" db:"last_accessed"`
}

// FileMapping maps a user's file to deduplicated content
type FileMapping struct {
    FileID       uuid.UUID `json:"file_id" db:"file_id"`
    UserID       uuid.UUID `json:"user_id" db:"user_id"`
    ContentHash  string    `json:"content_hash" db:"content_hash"`
    OriginalName string    `json:"original_name" db:"original_name"`
    CreatedAt    time.Time `json:"created_at" db:"created_at"`
}

// DedupStats provides deduplication statistics
type DedupStats struct {
    TotalFiles       int   `json:"total_files"`
    UniqueBlocks     int   `json:"unique_blocks"`
    DuplicateFiles   int   `json:"duplicate_files"`
    SpaceSaved       int64 `json:"space_saved"`       // Bytes saved through dedup
    DeduplicationRatio float64 `json:"dedup_ratio"`   // Ratio of saved space
}

// Service defines the deduplication service interface
type Service interface {
    // CheckDuplicate checks if content already exists and returns the entry if found.
    // Uses streaming hash computation to avoid loading entire file into memory.
    CheckDuplicate(ctx context.Context, reader io.Reader) (*DedupEntry, string, error)

    // Store stores new content and creates a dedup entry.
    // If content already exists, increments reference count instead.
    // Returns the content hash and any error.
    Store(ctx context.Context, userID uuid.UUID, reader io.Reader, size int64, filename string) (string, error)

    // Reference increments the reference count for existing content.
    // Used when a user uploads content that already exists.
    Reference(ctx context.Context, userID uuid.UUID, contentHash string, fileID uuid.UUID, filename string) error

    // Dereference decrements the reference count when a file is deleted.
    // If count reaches zero, schedules content for garbage collection.
    Dereference(ctx context.Context, fileID uuid.UUID) error

    // GetEntry retrieves a dedup entry by content hash.
    GetEntry(ctx context.Context, contentHash string) (*DedupEntry, error)

    // GetFileMapping retrieves the mapping for a user's file.
    GetFileMapping(ctx context.Context, fileID uuid.UUID) (*FileMapping, error)

    // GetUserDuplicates finds files owned by user that are duplicates of other files.
    GetUserDuplicates(ctx context.Context, userID uuid.UUID) ([]FileMapping, error)

    // GetStats returns deduplication statistics for a user (or global if userID is nil).
    GetStats(ctx context.Context, userID *uuid.UUID) (*DedupStats, error)

    // RunGarbageCollection removes content blocks with zero references.
    // Should be run periodically via a background job.
    RunGarbageCollection(ctx context.Context) (int, error)
}
```

### Required Structs/Types

```go
// service implements the Service interface
type service struct {
    db       *sql.DB
    storage  *storage.Service
    config   *config.Config
    mu       sync.RWMutex
    gcTicker *time.Ticker
}

// NewService creates a new deduplication service
func NewService(cfg *config.Config, storageService *storage.Service) (Service, error)
```

### Database Schema (for reference)

```sql
CREATE TABLE dedup_entries (
    content_hash VARCHAR(64) PRIMARY KEY,
    storage_key VARCHAR(512) NOT NULL,
    size BIGINT NOT NULL,
    ref_count INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_accessed TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE file_mappings (
    file_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    content_hash VARCHAR(64) NOT NULL REFERENCES dedup_entries(content_hash),
    original_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_file_mappings_user ON file_mappings(user_id);
CREATE INDEX idx_file_mappings_hash ON file_mappings(content_hash);
CREATE INDEX idx_dedup_entries_refcount ON dedup_entries(ref_count) WHERE ref_count = 0;
```

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/dedup_test.go`):
   - [ ] TestCheckDuplicate_NewContent - returns nil entry for new content
   - [ ] TestCheckDuplicate_ExistingContent - returns entry for duplicate
   - [ ] TestStore_NewContent - stores and returns hash
   - [ ] TestStore_DuplicateContent - increments ref count, does not re-store
   - [ ] TestReference_Success - creates mapping and increments count
   - [ ] TestDereference_DecrementCount - decrements count correctly
   - [ ] TestDereference_LastReference - marks for GC when count reaches 0
   - [ ] TestGetStats_Calculation - correctly calculates dedup ratio
   - [ ] TestGarbageCollection_RemovesZeroRef - removes orphaned blocks
   - [ ] TestGarbageCollection_PreservesReferenced - keeps blocks with refs > 0
   - [ ] TestConcurrentStore_SameContent - handles race conditions correctly

2. **Integration Points**:
   - [ ] Integrates with existing `storage.Service` for object storage
   - [ ] Uses same database connection patterns as `repository.FileRepository`
   - [ ] Follows error handling conventions from existing services

3. **Concurrency Safety**:
   - [ ] Thread-safe reference counting
   - [ ] Proper mutex usage (avoid A2/A5 bug patterns)
   - [ ] Graceful handling of concurrent uploads of same content

4. **Coverage**: Minimum 80% code coverage

---

## Task 2: Thumbnail Generation Service

### Overview

Implement an asynchronous thumbnail generation service for image and document files. The service should generate thumbnails of configurable sizes, cache results, and handle various file formats.

### Location

Create new files at:
- `internal/services/thumbnail/thumbnail.go`
- `internal/services/thumbnail/processor.go`
- `internal/services/thumbnail/cache.go`
- `tests/unit/thumbnail_test.go`

### Interface Contract

```go
package thumbnail

import (
    "context"
    "io"

    "github.com/google/uuid"
)

// Size represents a thumbnail size preset
type Size string

const (
    SizeSmall  Size = "small"  // 64x64
    SizeMedium Size = "medium" // 256x256
    SizeLarge  Size = "large"  // 512x512
    SizeCustom Size = "custom"
)

// Thumbnail represents a generated thumbnail
type Thumbnail struct {
    FileID      uuid.UUID `json:"file_id"`
    Size        Size      `json:"size"`
    Width       int       `json:"width"`
    Height      int       `json:"height"`
    Format      string    `json:"format"` // "jpeg", "png", "webp"
    StorageKey  string    `json:"storage_key"`
    ContentType string    `json:"content_type"`
    Generated   time.Time `json:"generated"`
    CacheHit    bool      `json:"cache_hit"` // For stats
}

// GenerateOptions configures thumbnail generation
type GenerateOptions struct {
    Width       int    // Custom width (only with SizeCustom)
    Height      int    // Custom height (only with SizeCustom)
    Format      string // Output format (default: "jpeg")
    Quality     int    // JPEG quality 1-100 (default: 85)
    Crop        bool   // Crop to exact dimensions vs. fit within
    Background  string // Background color for transparent images (default: "#FFFFFF")
}

// JobStatus represents the status of an async generation job
type JobStatus struct {
    JobID     string    `json:"job_id"`
    FileID    uuid.UUID `json:"file_id"`
    Size      Size      `json:"size"`
    Status    string    `json:"status"` // "pending", "processing", "completed", "failed"
    Error     string    `json:"error,omitempty"`
    Progress  int       `json:"progress"` // 0-100
    CreatedAt time.Time `json:"created_at"`
    UpdatedAt time.Time `json:"updated_at"`
}

// Service defines the thumbnail generation service interface
type Service interface {
    // Generate creates a thumbnail synchronously.
    // Returns the thumbnail metadata and a reader for the content.
    Generate(ctx context.Context, fileID uuid.UUID, size Size, opts *GenerateOptions) (*Thumbnail, io.ReadCloser, error)

    // GenerateAsync queues thumbnail generation for background processing.
    // Returns a job ID for status tracking.
    GenerateAsync(ctx context.Context, fileID uuid.UUID, size Size, opts *GenerateOptions) (string, error)

    // GetJobStatus returns the status of an async generation job.
    GetJobStatus(ctx context.Context, jobID string) (*JobStatus, error)

    // Get retrieves a previously generated thumbnail.
    // Returns nil if thumbnail doesn't exist (not an error).
    Get(ctx context.Context, fileID uuid.UUID, size Size) (*Thumbnail, io.ReadCloser, error)

    // GetAll retrieves all thumbnails for a file.
    GetAll(ctx context.Context, fileID uuid.UUID) ([]Thumbnail, error)

    // Invalidate removes cached thumbnails for a file.
    // Should be called when the source file is updated.
    Invalidate(ctx context.Context, fileID uuid.UUID) error

    // InvalidateAll removes all cached thumbnails (admin operation).
    InvalidateAll(ctx context.Context) error

    // GetSupportedFormats returns list of input formats that can be thumbnailed.
    GetSupportedFormats() []string

    // IsSupported checks if a MIME type can be thumbnailed.
    IsSupported(mimeType string) bool

    // Warmup pre-generates thumbnails for a file in all standard sizes.
    // Useful for batch processing during upload.
    Warmup(ctx context.Context, fileID uuid.UUID) error
}
```

### Required Structs/Types

```go
// service implements the Service interface
type service struct {
    db          *sql.DB
    storage     *storage.Service
    fileRepo    *repository.FileRepository
    redis       *redis.Client
    config      *config.Config
    jobQueue    chan *generateJob
    workers     int
    workerWg    sync.WaitGroup
    shutdownCh  chan struct{}
}

// generateJob represents a queued thumbnail generation job
type generateJob struct {
    JobID   string
    FileID  uuid.UUID
    Size    Size
    Options *GenerateOptions
    Done    chan error
}

// processor handles image processing operations
type processor struct {
    tempDir string
}

// cache handles thumbnail caching in Redis
type cache struct {
    redis  *redis.Client
    prefix string
    ttl    time.Duration
}

// NewService creates a new thumbnail service with worker pool
func NewService(cfg *config.Config, storageService *storage.Service, fileRepo *repository.FileRepository, workerCount int) (Service, error)

// Shutdown gracefully stops the worker pool
func (s *service) Shutdown(ctx context.Context) error
```

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/thumbnail_test.go`):
   - [ ] TestGenerate_SmallSize - generates 64x64 thumbnail
   - [ ] TestGenerate_MediumSize - generates 256x256 thumbnail
   - [ ] TestGenerate_LargeSize - generates 512x512 thumbnail
   - [ ] TestGenerate_CustomSize - generates custom dimensions
   - [ ] TestGenerate_CropMode - crops to exact size
   - [ ] TestGenerate_FitMode - fits within bounds preserving aspect ratio
   - [ ] TestGenerate_UnsupportedFormat - returns appropriate error
   - [ ] TestGenerateAsync_QueueJob - job is queued and processed
   - [ ] TestGetJobStatus_Pending - returns pending status
   - [ ] TestGetJobStatus_Completed - returns completed with thumbnail
   - [ ] TestGetJobStatus_Failed - returns error details
   - [ ] TestGet_CacheHit - returns cached thumbnail
   - [ ] TestGet_CacheMiss - returns nil, no error
   - [ ] TestInvalidate_ClearsCache - removes all sizes for file
   - [ ] TestIsSupported_ImageFormats - recognizes jpeg, png, gif, webp
   - [ ] TestIsSupported_DocumentFormats - recognizes pdf (if supported)
   - [ ] TestWarmup_GeneratesAllSizes - creates small, medium, large
   - [ ] TestConcurrentGenerate_SameFile - handles race correctly

2. **Integration Points**:
   - [ ] Integrates with `storage.Service` for source files and thumbnail storage
   - [ ] Uses `repository.FileRepository` to fetch file metadata
   - [ ] Uses Redis for caching (same patterns as `notification.Service`)
   - [ ] Follows worker pool pattern with proper shutdown

3. **Concurrency Safety**:
   - [ ] Worker pool for async generation (avoid goroutine leaks - A1 pattern)
   - [ ] Proper channel usage (avoid deadlocks - A3 pattern)
   - [ ] Graceful shutdown with WaitGroup

4. **Coverage**: Minimum 80% code coverage

---

## Task 3: File Search Indexer

### Overview

Implement a full-text search indexer that maintains a searchable index of file metadata and content. The service should support real-time indexing on file changes and efficient querying with filters and facets.

### Location

Create new files at:
- `internal/services/search/indexer.go`
- `internal/services/search/query.go`
- `internal/services/search/analyzer.go`
- `tests/unit/search_test.go`

### Interface Contract

```go
package search

import (
    "context"
    "time"

    "github.com/google/uuid"
    "github.com/terminal-bench/cloudvault/internal/models"
)

// Document represents an indexed document
type Document struct {
    FileID       uuid.UUID         `json:"file_id"`
    UserID       uuid.UUID         `json:"user_id"`
    Name         string            `json:"name"`
    Path         string            `json:"path"`
    Extension    string            `json:"extension"`
    MimeType     string            `json:"mime_type"`
    Size         int64             `json:"size"`
    Content      string            `json:"content,omitempty"`  // Extracted text content
    Tags         []string          `json:"tags,omitempty"`
    Metadata     map[string]string `json:"metadata,omitempty"` // Custom metadata
    CreatedAt    time.Time         `json:"created_at"`
    UpdatedAt    time.Time         `json:"updated_at"`
    IndexedAt    time.Time         `json:"indexed_at"`
}

// SearchQuery represents a search request
type SearchQuery struct {
    Query      string            `json:"query"`                // Full-text search query
    UserID     uuid.UUID         `json:"user_id"`              // Required: scope to user
    Path       string            `json:"path,omitempty"`       // Filter by path prefix
    Extensions []string          `json:"extensions,omitempty"` // Filter by file extensions
    MimeTypes  []string          `json:"mime_types,omitempty"` // Filter by MIME types
    MinSize    int64             `json:"min_size,omitempty"`   // Minimum file size
    MaxSize    int64             `json:"max_size,omitempty"`   // Maximum file size
    DateFrom   *time.Time        `json:"date_from,omitempty"`  // Created after
    DateTo     *time.Time        `json:"date_to,omitempty"`    // Created before
    Tags       []string          `json:"tags,omitempty"`       // Must have all tags
    SortBy     string            `json:"sort_by,omitempty"`    // "relevance", "name", "date", "size"
    SortOrder  string            `json:"sort_order,omitempty"` // "asc", "desc"
    Offset     int               `json:"offset,omitempty"`
    Limit      int               `json:"limit,omitempty"`      // Default: 20, Max: 100
}

// SearchResult represents a search response
type SearchResult struct {
    Documents    []DocumentHit     `json:"documents"`
    Total        int               `json:"total"`         // Total matching documents
    Took         time.Duration     `json:"took"`          // Query execution time
    Facets       map[string][]Facet `json:"facets,omitempty"`
    Suggestions  []string          `json:"suggestions,omitempty"` // Did-you-mean suggestions
}

// DocumentHit is a matched document with relevance score
type DocumentHit struct {
    Document   Document          `json:"document"`
    Score      float64           `json:"score"`
    Highlights map[string]string `json:"highlights,omitempty"` // Field -> highlighted text
}

// Facet represents a facet value with count
type Facet struct {
    Value string `json:"value"`
    Count int    `json:"count"`
}

// IndexStats provides indexing statistics
type IndexStats struct {
    TotalDocuments   int       `json:"total_documents"`
    IndexSize        int64     `json:"index_size_bytes"`
    LastIndexed      time.Time `json:"last_indexed"`
    PendingDocuments int       `json:"pending_documents"`
    IndexingRate     float64   `json:"indexing_rate"` // docs/second
}

// Service defines the search indexer service interface
type Service interface {
    // Index adds or updates a document in the index.
    Index(ctx context.Context, file *models.File, content string) error

    // IndexBatch indexes multiple documents efficiently.
    IndexBatch(ctx context.Context, files []models.File) error

    // Delete removes a document from the index.
    Delete(ctx context.Context, fileID uuid.UUID) error

    // DeleteByUser removes all documents for a user.
    DeleteByUser(ctx context.Context, userID uuid.UUID) error

    // Search performs a full-text search with filters.
    Search(ctx context.Context, query *SearchQuery) (*SearchResult, error)

    // Suggest returns search suggestions based on partial query.
    Suggest(ctx context.Context, userID uuid.UUID, prefix string, limit int) ([]string, error)

    // Reindex rebuilds the entire index from the database.
    // Should be run as a background job.
    Reindex(ctx context.Context, userID *uuid.UUID) error

    // GetDocument retrieves a single indexed document.
    GetDocument(ctx context.Context, fileID uuid.UUID) (*Document, error)

    // UpdateTags updates the tags for a document.
    UpdateTags(ctx context.Context, fileID uuid.UUID, tags []string) error

    // GetStats returns indexing statistics.
    GetStats(ctx context.Context, userID *uuid.UUID) (*IndexStats, error)

    // Subscribe returns a channel for real-time index updates.
    // Useful for monitoring indexing progress.
    Subscribe(ctx context.Context, userID uuid.UUID) (<-chan IndexEvent, func())
}

// IndexEvent represents an indexing event
type IndexEvent struct {
    Type     string    `json:"type"` // "indexed", "deleted", "error"
    FileID   uuid.UUID `json:"file_id"`
    FileName string    `json:"file_name"`
    Error    string    `json:"error,omitempty"`
    Time     time.Time `json:"time"`
}
```

### Required Structs/Types

```go
// service implements the Service interface
type service struct {
    db          *sql.DB
    redis       *redis.Client
    fileRepo    *repository.FileRepository
    config      *config.Config
    indexMu     sync.RWMutex
    subscribers map[string][]chan IndexEvent
    subMu       sync.RWMutex
    indexQueue  chan *indexJob
    workerWg    sync.WaitGroup
    shutdownCh  chan struct{}
}

// indexJob represents a queued indexing job
type indexJob struct {
    File    *models.File
    Content string
    Delete  bool
}

// analyzer handles text analysis for indexing
type analyzer struct {
    stopWords map[string]bool
    stemmer   func(string) string
}

// queryBuilder builds search queries
type queryBuilder struct {
    query *SearchQuery
}

// NewService creates a new search indexer service
func NewService(cfg *config.Config, fileRepo *repository.FileRepository, workerCount int) (Service, error)

// Shutdown gracefully stops the indexer
func (s *service) Shutdown(ctx context.Context) error
```

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/search_test.go`):
   - [ ] TestIndex_NewDocument - indexes new file correctly
   - [ ] TestIndex_UpdateDocument - updates existing document
   - [ ] TestIndexBatch_MultipleFiles - indexes batch efficiently
   - [ ] TestDelete_RemovesDocument - document no longer searchable
   - [ ] TestSearch_SimpleQuery - finds matching documents
   - [ ] TestSearch_WithFilters - applies extension/size/date filters
   - [ ] TestSearch_PathPrefix - filters by path correctly
   - [ ] TestSearch_Pagination - offset and limit work correctly
   - [ ] TestSearch_Sorting - sorts by name/date/size/relevance
   - [ ] TestSearch_Highlights - returns highlighted matches
   - [ ] TestSearch_Facets - returns faceted counts
   - [ ] TestSearch_NoResults - returns empty result, not error
   - [ ] TestSuggest_ReturnsMatches - returns suggestions for prefix
   - [ ] TestUpdateTags_Success - tags are updated and searchable
   - [ ] TestSubscribe_ReceivesEvents - subscription works correctly
   - [ ] TestReindex_RebuildIndex - rebuilds from database
   - [ ] TestConcurrentIndex_Consistency - handles concurrent updates

2. **Integration Points**:
   - [ ] Uses `repository.FileRepository` for file metadata
   - [ ] Uses Redis for search index and caching (like `notification.Service`)
   - [ ] Follows subscription pattern from `sync.Service.WatchChanges`
   - [ ] Worker pool for async indexing

3. **Concurrency Safety**:
   - [ ] Thread-safe index updates with proper locking
   - [ ] Subscription cleanup on context cancellation (avoid goroutine leaks)
   - [ ] Proper channel usage with select for cancellation

4. **Query Features**:
   - [ ] Case-insensitive search
   - [ ] Partial word matching (prefix search)
   - [ ] Boolean operators (AND/OR) in query string
   - [ ] Phrase matching with quotes

5. **Coverage**: Minimum 80% code coverage

---

## General Requirements

### Code Quality

1. Follow existing patterns in the codebase:
   - Constructor pattern: `NewService(cfg *config.Config) *Service`
   - Error wrapping: `fmt.Errorf("failed to X: %w", err)`
   - Context propagation in all database/storage operations
   - Proper resource cleanup with `defer`

2. Avoid common bug patterns documented in TASK.md:
   - A1: Goroutine leaks - always handle context cancellation
   - A2: Race conditions - use proper mutex/sync primitives
   - A3: Channel deadlocks - use buffered channels or select with timeout
   - C2: Connection leaks - always close rows/statements
   - D1: Ignored errors - check and handle all errors

3. Documentation:
   - Godoc comments on all exported types and functions
   - Inline comments for complex logic

### Testing

1. Use testify for assertions:
   ```go
   import "github.com/stretchr/testify/assert"
   ```

2. Use table-driven tests where appropriate

3. Mock external dependencies (database, Redis, storage)

4. Test error paths, not just happy paths

### Configuration

Add any new config fields to `internal/config/config.go`:

```go
// Example additions
ThumbnailWorkers   int    // Number of thumbnail workers
SearchIndexPrefix  string // Redis prefix for search index
DedupGCInterval    time.Duration // Garbage collection interval
```

### Integration

New services should be wired up in `cmd/server/main.go` following existing patterns:

```go
// Example
dedupService, err := dedup.NewService(cfg, storageService)
if err != nil {
    log.Fatal("Failed to create dedup service:", err)
}
```
