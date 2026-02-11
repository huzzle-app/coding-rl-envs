# VectorHarbor - Alternative Tasks

## Overview

These five alternative tasks extend VectorHarbor's capabilities in different dimensions: implementing approximate nearest neighbor indexing strategies, refactoring similarity computation logic into a dedicated service, optimizing batch processing for concurrent workloads, adding metadata-based filtering to queries, and implementing zero-downtime schema migration for vector dimension changes.

## Environment

- **Language**: Rust 2021
- **Infrastructure**: Maritime orchestration platform with allocator, routing, policy, queue, security, resilience, statistics, workflow, and contract management modules
- **Difficulty**: Hyper-Principal (70-140h, ~21 bugs, 9200+ tests)

## Tasks

### Task 1: Feature Development - Approximate Nearest Neighbor (ANN) Index Support

Extend the allocator module to support index-aware resource allocation with HNSW, IVF-Flat, and LSH index types. The system should recognize index-specific operational states (building, serving, rebuilding) through the policy engine and prioritize queries over index updates during peak load. Statistics module must track index-specific metrics including recall rate, query latency percentiles, and build time.

### Task 2: Refactoring - Extract Vector Similarity Service

Consolidate similarity computation logic scattered across allocator, routing, and statistics modules into a dedicated, trait-based service supporting cosine, euclidean, dot product, and hamming distance metrics. Update routing for channel scoring, statistics for distribution analysis, and resilience for checkpoint support. Reduce code duplication by at least 40% while maintaining all existing test compatibility.

### Task 3: Performance Optimization - Concurrent Vector Batch Processing

Enhance the queue and allocator to process batches concurrently across multiple CPU cores while maintaining FIFO ordering guarantees for vectors in the same namespace/partition. Improve throughput by at least 3x on multi-core systems. Update rate limiter and circuit breaker to correctly handle concurrent processing paths without deadlocks or race conditions.

### Task 4: API Extension - Vector Metadata Filtering

Add metadata support to the vector ingestion API (arbitrary key-value pairs), extend the query interface with filter expressions (equality, range, set membership, prefix matching), and update the routing layer to use metadata indexes for partition pruning. Implement metadata-based access control in the policy engine and track filter selectivity metrics in queue health monitoring.

### Task 5: Migration - Schema Versioning and Vector Dimension Migration

Implement a migration framework supporting dimension changes (padding, truncation, re-embedding) with dual-write mode for zero-downtime schema evolution. Extend the workflow engine to model migration as a multi-stage checkpointed process with rollback capability. Ensure the resilience module's replay functionality correctly handles cross-schema-version events.

## Getting Started

```bash
cargo test
```

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). All existing tests continue to pass after feature implementation.
