# DataNexus - Alternative Tasks

This document describes alternative tasks for the DataNexus real-time data pipeline and analytics platform. Each task represents a different type of engineering challenge that could be performed on this codebase.

---

## Task 1: Feature Development - Streaming Data Deduplication

### Description

Implement a streaming data deduplication system for the ingestion pipeline. The current ingestion service accepts all incoming records without checking for duplicates, which leads to inflated metrics, incorrect aggregations, and wasted storage in downstream systems.

The deduplication system needs to work in a distributed environment where multiple ingestion service instances may receive the same record due to at-least-once delivery guarantees from upstream sources. The system should support configurable deduplication windows (e.g., deduplicate records with the same ID within the last 5 minutes) and use memory-efficient probabilistic data structures for high-throughput scenarios.

The implementation should integrate with Redis for distributed state sharing across ingestion instances, support both exact deduplication (using record IDs) and fuzzy deduplication (using content hashing), and provide metrics for duplicate detection rates.

### Acceptance Criteria

- Records with identical IDs received within the deduplication window are dropped after the first occurrence
- Deduplication state is shared across all ingestion service instances via Redis
- Bloom filters are used for memory-efficient approximate deduplication at high throughput
- Exact deduplication is available for use cases requiring guaranteed uniqueness
- Configurable deduplication window size (default: 5 minutes, max: 1 hour)
- Duplicate detection metrics are exposed (total duplicates detected, deduplication ratio)
- Late-arriving duplicates (after window expiry) are handled gracefully with configurable policy
- All existing ingestion tests continue to pass

### Test Command

```bash
npm test
```

---

## Task 2: Refactoring - Unified Window State Management

### Description

The current window management implementation in the stream processing layer has grown organically and now contains duplicated logic across tumbling windows, sliding windows, and session windows. Each window type has its own state management, boundary calculations, and event assignment logic, leading to inconsistent behavior and maintenance burden.

Refactor the window management system to use a unified state management abstraction. The new design should extract common concerns (state storage, watermark tracking, late data handling) into shared components while preserving the unique semantics of each window type. This refactoring should also address the memory leak issues where closed window state is never cleaned up.

The refactored code should maintain backward compatibility with existing window configurations while enabling easier addition of new window types (such as count-based windows or global windows) in the future.

### Acceptance Criteria

- Common window state operations are extracted into a shared WindowStateManager class
- Each window type (tumbling, sliding, session) uses the shared state manager
- Closed window state is properly cleaned up based on watermark advancement
- Memory usage remains bounded regardless of the number of windows processed
- Window boundary calculations are consistent across all window types
- Late data handling follows the same policy across all window types
- New window types can be added by implementing a simple interface
- All existing stream processing tests continue to pass without modification

### Test Command

```bash
npm test
```

---

## Task 3: Performance Optimization - Query Engine Batch Processing

### Description

The query engine currently processes each query independently, even when multiple queries target the same underlying data or time range. This leads to redundant data fetches, repeated aggregation computations, and suboptimal resource utilization during dashboard refresh cycles when many widgets query similar data.

Optimize the query engine to support intelligent query batching and result sharing. When multiple queries arrive within a short time window and share common data requirements, they should be merged into a single underlying query with results distributed to all requesters. The optimization should also implement query result caching with proper invalidation based on data freshness requirements.

The implementation should be transparent to query callers - the existing query API should work unchanged, with batching happening automatically based on query analysis.

### Acceptance Criteria

- Queries with identical data source and time range are automatically batched
- Query results are cached with configurable TTL based on data freshness requirements
- Cache invalidation triggers when new data arrives for the queried time range
- Dashboard refresh with 20+ widgets completes in under 500ms (previously 2+ seconds)
- Query batching reduces database connections by at least 60% during peak load
- Partial result sharing works for queries with overlapping but not identical ranges
- Cache hit rate metrics are exposed for monitoring
- All existing query engine tests continue to pass

### Test Command

```bash
npm test
```

---

## Task 4: API Extension - Pipeline Versioning and Rollback

### Description

Add support for pipeline configuration versioning and rollback capabilities. Currently, pipeline configurations are updated in place with no history, making it impossible to recover from bad configuration changes or to audit what configuration was active during a specific time period.

The versioning system should maintain a complete history of pipeline configuration changes, support instant rollback to any previous version, and provide a diff view between versions. It should also integrate with the scheduler to automatically pause pipeline execution during configuration transitions and ensure exactly-once semantics during version switches.

The API extension should follow RESTful conventions and integrate with the existing authentication and authorization system to track who made each configuration change.

### Acceptance Criteria

- Each pipeline configuration change creates a new version with timestamp and author
- GET /pipelines/:id/versions returns paginated version history
- GET /pipelines/:id/versions/:version returns specific version configuration
- POST /pipelines/:id/rollback/:version atomically reverts to specified version
- GET /pipelines/:id/versions/:v1/diff/:v2 returns structured diff between versions
- Pipeline execution is paused during configuration transitions (no data loss)
- Version metadata includes change description, author, and timestamp
- Maximum of 100 versions retained per pipeline (oldest auto-pruned)
- All existing pipeline management tests continue to pass

### Test Command

```bash
npm test
```

---

## Task 5: Migration - Schema Registry to Protobuf Format

### Description

Migrate the connector framework's schema registry from JSON Schema to Protocol Buffers (protobuf) format. The current JSON Schema-based registry has performance limitations at scale: schema validation is CPU-intensive, schema size grows linearly with complexity, and there is no efficient binary serialization for high-throughput connectors.

The migration should support a transition period where both JSON Schema and protobuf schemas coexist, allowing gradual migration of existing connectors. The new protobuf-based registry should provide automatic schema evolution validation (backward/forward compatibility checks), efficient binary serialization for connector data transfer, and schema compilation to generate strongly-typed interfaces.

The migration should not require downtime and should maintain compatibility with existing connector configurations during the transition.

### Acceptance Criteria

- Schema registry accepts both JSON Schema and protobuf schema definitions
- Protobuf schemas are validated for backward compatibility on registration
- Connector data can be serialized/deserialized using registered protobuf schemas
- Schema evolution rules are enforced (no breaking changes to existing schemas)
- JSON Schema to protobuf migration tool converts existing schemas
- Schema compilation generates TypeScript interfaces for type safety
- Binary serialization reduces message size by at least 40% compared to JSON
- Graceful fallback to JSON when protobuf schema is unavailable
- All existing connector framework tests continue to pass

### Test Command

```bash
npm test
```
