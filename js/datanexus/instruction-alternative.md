# DataNexus - Alternative Tasks

## Overview

DataNexus includes 5 alternative task types that test different software engineering skills: feature development, refactoring, performance optimization, API design, and migration patterns. Each task uses the same real-time data pipeline codebase to solve domain-specific challenges.

## Environment

- **Language**: JavaScript (Node.js)
- **Infrastructure**: RabbitMQ, PostgreSQL, Redis, Consul, MinIO, TimescaleDB
- **Difficulty**: Distinguished
- **Services**: 15 microservices in a distributed data pipeline platform

## Tasks

### Task 1: Feature Development - Streaming Data Deduplication (Feature)

Implement a streaming data deduplication system for the ingestion pipeline. The current ingestion service accepts all incoming records without checking for duplicates, which leads to inflated metrics, incorrect aggregations, and wasted storage.

The deduplication system needs to work in a distributed environment where multiple ingestion service instances may receive the same record due to at-least-once delivery guarantees. The system should support configurable deduplication windows (e.g., deduplicate records with the same ID within the last 5 minutes) and use memory-efficient probabilistic data structures like Bloom filters for high-throughput scenarios.

The implementation should integrate with Redis for distributed state sharing, support both exact and fuzzy deduplication, and provide metrics for duplicate detection rates.

### Task 2: Refactoring - Unified Window State Management (Refactor)

The current window management implementation in the stream processing layer has grown organically and now contains duplicated logic across tumbling windows, sliding windows, and session windows. Each window type has its own state management, boundary calculations, and event assignment logic, leading to inconsistent behavior and maintenance burden.

Refactor the window management system to use a unified state management abstraction. The new design should extract common concerns (state storage, watermark tracking, late data handling) into shared components while preserving the unique semantics of each window type. This refactoring should also address memory leak issues where closed window state is never cleaned up.

The refactored code should maintain backward compatibility with existing window configurations while enabling easier addition of new window types in the future.

### Task 3: Performance Optimization - Query Engine Batch Processing (Optimize)

The query engine currently processes each query independently, even when multiple queries target the same underlying data or time range. This leads to redundant data fetches, repeated aggregation computations, and suboptimal resource utilization during dashboard refresh cycles when many widgets query similar data.

Optimize the query engine to support intelligent query batching and result sharing. When multiple queries arrive within a short time window and share common data requirements, they should be merged into a single underlying query with results distributed to all requesters. The optimization should also implement query result caching with proper invalidation based on data freshness requirements.

The implementation should be transparent to query callers, with batching happening automatically based on query analysis.

### Task 4: API Extension - Pipeline Versioning and Rollback (API)

Add support for pipeline configuration versioning and rollback capabilities. Currently, pipeline configurations are updated in place with no history, making it impossible to recover from bad configuration changes or audit what configuration was active during a specific time period.

The versioning system should maintain a complete history of pipeline configuration changes, support instant rollback to any previous version, and provide a diff view between versions. It should also integrate with the scheduler to automatically pause pipeline execution during configuration transitions and ensure exactly-once semantics during version switches.

The API extension should follow RESTful conventions and integrate with the existing authentication and authorization system to track who made each configuration change.

### Task 5: Migration - Schema Registry to Protobuf Format (Migration)

Migrate the connector framework's schema registry from JSON Schema to Protocol Buffers (protobuf) format. The current JSON Schema-based registry has performance limitations at scale: schema validation is CPU-intensive, schema size grows linearly with complexity, and there is no efficient binary serialization for high-throughput connectors.

The migration should support a transition period where both JSON Schema and protobuf schemas coexist, allowing gradual migration of existing connectors. The new protobuf-based registry should provide automatic schema evolution validation, efficient binary serialization for connector data transfer, and schema compilation to generate strongly-typed interfaces.

The migration should not require downtime and should maintain compatibility with existing connector configurations during the transition.

## Getting Started

```bash
cd js/datanexus

# Start infrastructure and services
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Run tests
npm test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).

Each task maintains all existing tests while adding new functionality or improving the system according to the specific task requirements.
