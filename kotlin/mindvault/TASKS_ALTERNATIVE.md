# MindVault - Alternative Tasks

These alternative tasks provide different entry points into the MindVault knowledge management platform. Each task focuses on a specific aspect of the system while requiring deep understanding of the existing codebase.

---

## Task 1: Implement Hierarchical Knowledge Graph Traversal (Feature Development)

### Description

MindVault's knowledge graph currently supports basic node-to-node edge traversal through `GraphService.findShortestPath()` and neighbor lookups. Users have requested the ability to perform hierarchical traversals that respect semantic relationships between concepts, such as "is-a", "part-of", and "related-to" edge types.

The new hierarchical traversal feature should allow users to query for all descendants of a concept node (following "is-a" and "part-of" edges), find common ancestors between two nodes, and compute the semantic distance between concepts based on their position in the hierarchy. This is critical for features like "show me all documents related to Machine Learning" where the system should automatically include documents tagged with sub-concepts like "Neural Networks" or "Deep Learning".

The implementation must integrate with the existing `GraphNode` sealed class hierarchy, respect the current caching mechanisms in `GraphService`, and be properly serializable for cross-service communication. Special attention should be paid to cycle detection in the graph and efficient traversal of large knowledge hierarchies.

### Acceptance Criteria

- Add a new `EdgeType` enum with values `IS_A`, `PART_OF`, `RELATED_TO`, and `REFERENCES` to the graph module
- Implement `findDescendants(nodeId: String, edgeTypes: Set<EdgeType>, maxDepth: Int): Flow<GraphNode>` that streams all descendant nodes
- Implement `findCommonAncestors(nodeA: String, nodeB: String): List<GraphNode>` that returns shared ancestor nodes ordered by proximity
- Implement `semanticDistance(nodeA: String, nodeB: String): Double` that computes normalized distance (0.0 = same node, 1.0 = unrelated)
- Handle cyclic graph structures gracefully without infinite loops or stack overflow
- Integrate with the existing `nodeCache` to avoid redundant database queries during traversal
- Add proper cancellation support for the `Flow`-based traversal operations
- Ensure all new serializable classes have explicit `@SerialName` annotations

### Test Command

```bash
./gradlew test
```

---

## Task 2: Refactor Document Versioning to Event Sourcing (Refactoring)

### Description

The current `DocumentService` uses a simple overwrite model for document updates, storing only the latest version in the database with an in-memory `versionCache`. This approach loses document history and makes it impossible to audit changes, implement undo/redo, or track collaborative edits over time.

The document storage should be refactored to use an event sourcing pattern where every change to a document (create, update metadata, update content, tag addition, tag removal, delete) is recorded as an immutable event. The current document state should be reconstructable by replaying events from the event store. This aligns with the existing `EventBus` infrastructure in the shared module.

The refactoring must maintain backward compatibility with existing API contracts while introducing the new event-sourced internals. Document snapshots should be periodically created to optimize read performance, avoiding full event replay for every document access. The existing `Document` data class structure should be preserved for API responses.

### Acceptance Criteria

- Create a sealed class hierarchy for `DocumentEvent` with subtypes: `DocumentCreated`, `ContentUpdated`, `MetadataUpdated`, `TagAdded`, `TagRemoved`, `DocumentDeleted`
- Each event must include `eventId`, `documentId`, `timestamp`, `userId`, and event-specific payload
- Implement `DocumentEventStore` that persists events to the database using Exposed
- Refactor `saveDocument()` to emit `DocumentCreated` or `ContentUpdated` events instead of direct database writes
- Implement `getDocumentHistory(documentId: String): List<DocumentEvent>` to retrieve change history
- Implement `getDocumentAtVersion(documentId: String, version: Int): Document` to reconstruct historical state
- Add snapshot creation after every N events (configurable, default 10) to optimize replay performance
- Ensure all event classes are properly serializable with kotlinx.serialization
- Maintain existing `Document` return type for all public API methods

### Test Command

```bash
./gradlew test
```

---

## Task 3: Optimize Embedding Similarity Search with Approximate Nearest Neighbors (Performance Optimization)

### Description

The `EmbeddingService.findSimilar()` method currently performs a brute-force linear scan through all cached embeddings, computing cosine similarity for each vector. This O(n) approach becomes prohibitively slow when the embedding cache grows beyond tens of thousands of documents, with users reporting 5+ second query times for large knowledge bases.

Implement an approximate nearest neighbor (ANN) index to achieve sub-linear query time for similarity searches. The implementation should use a locality-sensitive hashing (LSH) approach or a hierarchical navigable small world (HNSW) graph structure suitable for high-dimensional embedding vectors (1536 dimensions for OpenAI embeddings).

The optimization must gracefully degrade to exact search for small datasets where the indexing overhead is not justified. The index should support incremental updates as new embeddings are added without requiring full rebuilds. Memory usage should be carefully managed as the embedding cache can be substantial.

### Acceptance Criteria

- Implement an ANN index data structure that supports 1536-dimensional float vectors
- Achieve O(log n) or better average-case query time for `findSimilar()` with recall >= 0.95
- Add `rebuildIndex()` method for bulk index construction from existing embeddings
- Support incremental index updates via `addToIndex(documentId: String, embedding: EmbeddingVector)`
- Implement configurable accuracy/speed tradeoff via `IndexConfig(efSearch: Int, efConstruction: Int)`
- Fall back to exact brute-force search when cache size < 1000 embeddings
- Add `findSimilarWithScore(query: EmbeddingVector, topK: Int, minScore: Float): List<Pair<String, Float>>` with score filtering
- Ensure thread-safety for concurrent reads and writes to the index
- Memory overhead should not exceed 2x the raw embedding storage size

### Test Command

```bash
./gradlew test
```

---

## Task 4: Extend Search API with Semantic Query Understanding (API Extension)

### Description

The current `SearchService` supports basic keyword-based search through JDBC queries with simple text matching. Users have requested natural language query support that understands semantic intent, such as "documents about machine learning from last month" being parsed into a structured query with semantic filters.

Extend the search API to accept natural language queries and decompose them into structured `SearchQuery` objects. The extension should integrate with the embeddings service to perform hybrid search combining keyword matching (BM25-style) with semantic similarity (vector search). Query understanding should handle temporal expressions ("last week", "yesterday"), entity references ("by John", "in the ML folder"), and boolean operators expressed in natural language.

The API extension must maintain backward compatibility with existing keyword search while adding new endpoints and query parameters for semantic search. Results should include relevance explanations showing which signals (keyword match, semantic similarity, recency) contributed to the ranking.

### Acceptance Criteria

- Add `POST /search/semantic` endpoint that accepts `{ "query": "natural language query", "options": {...} }`
- Implement `QueryParser` that extracts structured filters from natural language (temporal, author, folder, tags)
- Support hybrid ranking that combines keyword BM25 scores with embedding cosine similarity
- Add `weightKeyword` and `weightSemantic` parameters to control hybrid ranking balance (default 0.5/0.5)
- Parse temporal expressions: "today", "yesterday", "last week", "last month", "this year", date ranges
- Return `SearchResultWithExplanation` that includes `keywordScore`, `semanticScore`, `finalScore`, and `matchedTerms`
- Implement query expansion using the knowledge graph to include related concepts
- Add rate limiting for semantic search (more expensive than keyword search)
- Ensure the query parser is injection-safe and validates all extracted parameters

### Test Command

```bash
./gradlew test
```

---

## Task 5: Migrate Synchronous Event Publishing to Async Kafka Streams (Migration)

### Description

The current `EventBus` in the shared module uses synchronous in-process event publishing, which creates tight coupling between services and blocks the caller until all event handlers complete. This architecture prevents horizontal scaling and creates latency spikes when event handlers are slow.

Migrate the event publishing infrastructure to use Apache Kafka for asynchronous, durable event streaming. The migration must be performed incrementally to avoid a big-bang cutover that could cause data loss or service outages. During the migration period, events should be published to both the legacy in-process bus and Kafka, with consumers gradually migrating to Kafka.

The migration should leverage the existing Kafka infrastructure defined in docker-compose.yml and fix any serialization issues with the current Kafka producer configuration. Event ordering guarantees must be preserved for events with the same partition key (typically document ID or user ID). Consumer groups should be used to enable parallel processing while maintaining per-partition ordering.

### Acceptance Criteria

- Create `KafkaEventPublisher` that implements the same interface as the current `EventBus`
- Implement dual-write mode that publishes to both in-process and Kafka during migration
- Add `@KafkaEvent` annotation to mark event classes with their topic and partition key strategy
- Implement `KafkaEventConsumer` with consumer group support and automatic offset management
- Add dead letter queue handling for events that fail processing after N retries (configurable)
- Ensure exactly-once semantics for event publishing using Kafka transactions
- Create migration toggle in configuration: `events.mode = "legacy" | "dual" | "kafka"`
- Implement event schema registry integration for backward-compatible schema evolution
- Add metrics for event publishing latency, consumer lag, and dead letter queue depth
- Ensure all event serialization uses `ByteArraySerializer` with proper JSON encoding

### Test Command

```bash
./gradlew test
```
