# HelixOps - Alternative Tasks

## Overview

HelixOps supports 5 alternative task types beyond debugging: feature development for multi-tenant API key management, refactoring query builders into a unified DSL, optimizing coroutine-based connection pooling, extending APIs with a GraphQL federation gateway, and migrating the document module to event sourcing. Each task tests different software engineering skills within the same production codebase.

## Environment

- **Language**: Kotlin
- **Infrastructure**: Docker compose with PostgreSQL, Redis, and Ktor
- **Difficulty**: Apex-Principal (1250 bugs, 12,000+ tests for debugging tier)

## Tasks

### Task 1: Feature Development - Multi-Tenant API Key Management (Feature)

Extend HelixOps' JWT-based authentication with long-lived API keys for CI/CD and automated tooling. Keys must support configurable scopes, rate limiting, IP allowlisting, and propagated revocation across gateway instances within 5 seconds via the event bus. Enterprise customers require audit logging and key hierarchy (organization-level keys spawning service-scoped children). The feature integrates with the existing authentication pipeline while maintaining JWT security guarantees.

**Acceptance**: API keys CRUD, per-key rate limiting, scope validation, usage audit logging, revocation propagation, IP allowlisting, unified JWT+key authentication interface.

### Task 2: Refactoring - Unified Query Builder with Type-Safe DSL (Refactor)

The search, documents, graph, and analytics modules each implement custom query-building DSLs with inconsistent APIs and duplicated logic. Extract common patterns into a shared, type-safe builder leveraging Kotlin's DSL capabilities with proper scope control. Support composable filters, sorting, cursor-based pagination, field projection, and both Exposed ORM and raw JDBC backends. Migrate existing modules to the new builder while maintaining backward compatibility and reducing code duplication by 40%+.

**Acceptance**: Shared query builder in shared module with DslMarker annotations, type-safe field references, offset/cursor pagination, fluent AND/OR/NOT filters, migration of documents/search/graph modules, abstracted query execution, zero performance regression, all existing tests pass.

### Task 3: Performance Optimization - Coroutine-Based Connection Pooling (Optimize)

Current database access suffers from connection exhaustion under load. Implement a coroutine-aware connection pool with Kotlin's structured concurrency, properly handling cancellation so cancelled coroutines return connections rather than leaking them. Suspending connection acquisition allows coroutines to yield while waiting. Address transaction isolation issues in the billing module's concurrent credit transfers (lost updates). Expose pool metrics through analytics.

**Acceptance**: Coroutine-aware connection pool in shared database module, suspending connection acquisition respecting cancellation, configurable min/max/idle timeout, documents flow releases on cancellation, billing transfers use proper isolation levels, analytics metrics (active/idle/waiting), 10x improvement in concurrent capacity, no connection leaks under stress.

### Task 4: API Extension - GraphQL Federation Gateway (API)

Expose REST APIs across modules via a unified GraphQL interface that federates queries across documents, search, graph, and analytics. Query planning optimizes for minimal round-trips with request batching and parallelization. Authentication context propagates to backends. Error handling returns partial results with clear failure indication. Rate limiting and request costing apply at the GraphQL operation level.

**Acceptance**: GraphQL schema for documents/search/graph/analytics, multi-service queries with automatic planning, mutations for CRUD/notifications/billing, auth context propagation, DataLoader-style batching for N+1 prevention, partial failure with error fields, query complexity analysis, WebSocket subscriptions for real-time notifications.

### Task 5: Migration - Event Sourcing for Document Lifecycle (Migration)

Convert the documents module from traditional CRUD to event-sourced architecture where all changes become immutable events. Document state becomes a projection rebuilt from the event stream. Migrate existing documents with synthetic "DocumentCreated" events. Event store integrates with the event bus for real-time projections and supports batch replay. Snapshot optimization prevents unbounded replay. Zero-downtime migration with parallel operation of old and new systems.

**Acceptance**: All document operations emit domain events, state reconstructible at any timestamp, existing documents migrated with synthetic events, automatic snapshots, search index rebuilt as projection, event versioning for schema evolution, parallel old/new system operation, audit queries for complete history.

## Getting Started

```bash
./gradlew test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
