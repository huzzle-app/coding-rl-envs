# HelixOps - Alternative Tasks

## Task 1: Feature Development - Multi-Tenant API Key Management

### Description

HelixOps currently uses JWT-based authentication for all API access. Enterprise customers are requesting support for long-lived API keys that can be programmatically managed, rotated, and scoped to specific services. This feature is critical for enabling CI/CD pipelines and automated tooling to interact with the HelixOps platform without requiring interactive OAuth flows.

The API key system must integrate with the existing authentication pipeline in the gateway module while maintaining the security guarantees provided by the current JWT infrastructure. Keys should support configurable expiration policies, rate limiting per key, and audit logging of all key usage. The system must also support key hierarchy where organization-level keys can spawn service-scoped child keys.

Additionally, the feature must handle key revocation that propagates across all gateway instances within the SLA window, preventing stale keys from being accepted after revocation. This requires coordination with the existing caching infrastructure and event bus for real-time invalidation.

### Acceptance Criteria

- API keys can be created, listed, rotated, and revoked through authenticated endpoints
- Keys support configurable scopes limiting access to specific services (documents, search, billing, etc.)
- Rate limiting is enforced per-key with configurable thresholds stored in key metadata
- Key usage is logged to the analytics service with correlation IDs for audit trails
- Revocation propagates to all gateway instances within 5 seconds via the event bus
- Keys support optional IP allowlisting stored in key metadata
- The authentication service validates both JWT tokens and API keys through a unified interface
- Existing JWT-based authentication continues to work without modification

### Test Command

```bash
./gradlew test
```

---

## Task 2: Refactoring - Unified Query Builder with Type-Safe DSL

### Description

The search module currently uses a custom DSL for building queries, but similar query-building patterns are duplicated across the documents, graph, and analytics modules with inconsistent APIs. Each module has developed its own approach to constructing database queries, filtering results, and handling pagination, leading to maintenance burden and inconsistent behavior.

This refactoring task involves extracting the common query-building logic into a shared, type-safe DSL that can be used across all modules. The new query builder should leverage Kotlin's DSL capabilities with proper scope control to prevent accidental access to outer builder contexts. The builder must support composable filters, sorting specifications, pagination with cursor-based navigation, and projection of specific fields.

The refactored system should maintain backward compatibility with existing query patterns while providing a migration path to the new unified API. All existing tests must continue to pass, and the new builder should reduce code duplication by at least 40% across the affected modules.

### Acceptance Criteria

- A shared query builder DSL is available in the shared module with proper DslMarker annotations
- The builder supports type-safe field references that catch invalid field names at compile time
- Pagination supports both offset-based and cursor-based strategies with automatic cursor encoding
- Filter composition uses a fluent API supporting AND, OR, and NOT operations with correct precedence
- The documents, search, and graph modules are migrated to use the shared builder
- Query execution is abstracted to support both Exposed ORM and raw JDBC backends
- Performance benchmarks show no regression compared to hand-written queries
- All existing search, document, and graph query tests pass without modification

### Test Command

```bash
./gradlew test
```

---

## Task 3: Performance Optimization - Coroutine-Based Connection Pooling

### Description

The current database access patterns in HelixOps suffer from connection management issues that cause performance degradation under load. Multiple services open direct JDBC connections without pooling, leading to connection exhaustion during traffic spikes. The document streaming flow and search operations are particularly affected, as they hold connections open for extended periods during result iteration.

This optimization task requires implementing a coroutine-aware connection pool that integrates with Kotlin's structured concurrency model. The pool must properly handle cancellation, ensuring that cancelled coroutines release their connections back to the pool rather than leaking them. The implementation should use suspending functions for connection acquisition, allowing coroutines to yield while waiting for available connections rather than blocking threads.

The solution must also address the existing issues with transaction isolation in the billing module, where concurrent credit transfers can cause lost updates. The new pooling system should support configurable isolation levels per-transaction and integrate with the Exposed ORM's transaction management.

### Acceptance Criteria

- A coroutine-aware connection pool is implemented in the shared database module
- Connection acquisition is a suspending operation that respects coroutine cancellation
- Pool configuration supports min/max connections, idle timeout, and connection validation
- The documents flow properly releases connections when collection is cancelled
- The billing transfer operations use appropriate isolation levels to prevent lost updates
- Pool metrics are exposed through the analytics service (active, idle, waiting counts)
- Load tests demonstrate 10x improvement in concurrent request handling capacity
- No connection leaks occur under cancellation stress testing

### Test Command

```bash
./gradlew test
```

---

## Task 4: API Extension - GraphQL Federation Gateway

### Description

HelixOps exposes REST APIs across its various modules, but enterprise customers are requesting a unified GraphQL interface that can federate queries across documents, search, graph, and analytics services. The GraphQL gateway should provide a single entry point for clients while delegating field resolution to the appropriate backend services.

The federation layer must handle authentication consistently, propagating JWT claims and API keys to downstream services. Query planning should optimize for minimal round-trips by batching requests to the same service and parallelizing requests to independent services. The gateway must also implement proper error handling, returning partial results when some services fail while clearly indicating which fields could not be resolved.

The implementation should leverage Kotlin coroutines for concurrent resolver execution and integrate with the existing Ktor pipeline for HTTP handling. Rate limiting and request costing should be applied at the GraphQL operation level, not just per-HTTP-request, to prevent expensive queries from overwhelming backend services.

### Acceptance Criteria

- A GraphQL schema is defined that exposes documents, search results, graph nodes, and analytics
- Queries can span multiple services in a single request with automatic query planning
- Mutations for document CRUD, notification sending, and billing operations are supported
- Authentication context is propagated to all resolver executions
- N+1 query patterns are addressed through DataLoader-style batching
- Partial failure returns resolved fields with errors for failed fields
- Query complexity analysis rejects operations exceeding configurable thresholds
- Subscription support enables real-time document change notifications via WebSocket

### Test Command

```bash
./gradlew test
```

---

## Task 5: Migration - Event Sourcing for Document Lifecycle

### Description

The documents module currently uses a traditional CRUD approach where document updates overwrite previous state. This makes it impossible to audit document history, implement undo functionality, or replay events for disaster recovery. Enterprise compliance requirements demand a complete audit trail of all document modifications with the ability to reconstruct document state at any point in time.

This migration task involves converting the documents module to an event-sourced architecture where all changes are captured as immutable events. The current document state becomes a projection rebuilt from the event stream. The migration must handle existing documents by generating synthetic "DocumentCreated" events that capture their current state, allowing the system to operate consistently after migration.

The event store must integrate with the existing event bus for real-time projections while also supporting batch replay for rebuilding read models. Snapshot optimization should prevent unbounded event replay for frequently-modified documents. The migration must be performed with zero downtime, supporting a gradual rollout where old and new systems operate in parallel.

### Acceptance Criteria

- All document operations (create, update, delete, share) emit domain events to an event store
- Document state can be reconstructed at any point in time by replaying events up to that timestamp
- Existing documents are migrated with synthetic creation events preserving current state
- Snapshots are automatically created after configurable event counts to optimize replay
- The search index is rebuilt as a projection from the event stream
- Event versioning supports schema evolution for future event format changes
- The migration supports parallel operation of old and new systems during transition
- Audit queries can retrieve the complete history of changes for any document

### Test Command

```bash
./gradlew test
```
