# MindVault - Alternative Tasks

## Overview

These 5 alternative tasks provide different entry points into the MindVault knowledge management platform, testing feature development, refactoring, performance optimization, API extension, and migration skills. Each task focuses on a specific aspect of the system while requiring deep understanding of the existing codebase.

## Environment

- **Language**: Kotlin 1.9 | Ktor 2.3 | Exposed ORM
- **Infrastructure**: PostgreSQL 16, Redis 7, Kafka 3.6, Consul 1.17
- **Difficulty**: Principal (8-16 hours)

## Tasks

### Task 1: Implement Hierarchical Knowledge Graph Traversal (Feature Development)

Implement a new hierarchical traversal feature that respects semantic relationships between concepts ("is-a", "part-of", "related-to" edge types). This is critical for queries like "show me all documents related to Machine Learning" where the system should automatically include documents tagged with sub-concepts like "Neural Networks" or "Deep Learning".

Add new `EdgeType` enum, implement `findDescendants()`, `findCommonAncestors()`, and `semanticDistance()` functions, handle cyclic graph structures gracefully, and integrate with the existing caching mechanisms.

### Task 2: Refactor Document Versioning to Event Sourcing (Refactoring)

Refactor the `DocumentService` from a simple overwrite model to an event sourcing pattern where every change (create, update, tag operations, delete) is recorded as an immutable event. Implement `DocumentEventStore`, convert `saveDocument()` to emit events, reconstruct historical state with `getDocumentAtVersion()`, and add snapshot creation for read performance optimization while maintaining backward compatibility.

### Task 3: Optimize Embedding Similarity Search with Approximate Nearest Neighbors (Performance Optimization)

Implement an approximate nearest neighbor (ANN) index using locality-sensitive hashing (LSH) or hierarchical navigable small world (HNSW) to replace the current O(n) brute-force linear scan. Achieve O(log n) query time with >= 0.95 recall, support incremental updates, gracefully degrade to exact search for small datasets, and carefully manage memory usage for 1536-dimensional vectors.

### Task 4: Extend Search API with Semantic Query Understanding (API Extension)

Add a new `POST /search/semantic` endpoint that accepts natural language queries and decomposes them into structured `SearchQuery` objects. Implement `QueryParser` for extracting temporal expressions ("last week"), entity references ("by John"), and boolean operators. Support hybrid ranking combining BM25 keyword scores with embedding cosine similarity, return `SearchResultWithExplanation` with match justifications, and add rate limiting for the more expensive semantic search.

### Task 5: Migrate Synchronous Event Publishing to Async Kafka Streams (Migration)

Migrate the in-process `EventBus` to Apache Kafka for asynchronous, durable event streaming. Implement dual-write mode (legacy + Kafka), create `KafkaEventPublisher` and `KafkaEventConsumer` with consumer groups, add dead letter queue handling with retries, ensure exactly-once semantics using Kafka transactions, and include schema registry integration for backward-compatible schema evolution.

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/kotlin/mindvault

# Start infrastructure and services
docker compose up -d

# Run tests
./gradlew test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). Each task includes specific functional requirements, test coverage minimums (25-35 unit tests + 10-15 integration tests), and architectural patterns to follow.
