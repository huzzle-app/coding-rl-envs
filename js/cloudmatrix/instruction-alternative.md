# CloudMatrix - Alternative Tasks

## Overview

CloudMatrix supports five alternative task types beyond the primary debugging challenge. These tasks provide different engineering disciplines: adding complex new features with metered billing, refactoring permission logic into a shared engine, optimizing search indexing performance, extending APIs for audit compliance, and migrating document storage to event sourcing.

## Environment

- **Language**: JavaScript (Node.js)
- **Infrastructure**: RabbitMQ, PostgreSQL, Redis, Elasticsearch, MinIO, Consul
- **Difficulty**: Distinguished (24-48 hours)

## Tasks

### Task 1: Feature Development - Usage-Based Billing with Metered Seats

Implement a metered billing system that tracks real-time usage across multiple dimensions: active document collaborators, storage consumption, API calls, and compute time for document processing. The system must support per-minute granularity for billing events, handle burst usage gracefully, and provide customers with real-time cost projections. Integration with the existing subscription service is required, allowing hybrid models where base subscriptions include bundled usage with overage charges.

### Task 2: Refactoring - Extract Shared Permission Evaluation Engine

Refactor duplicated permission checking logic across multiple services (gateway middleware, permissions service, documents service, presence service) into a unified evaluation engine. The engine should support a policy language with inheritance hierarchies (organization > team > folder > document), role-based conditions, and attribute-based policies. Must support both embedded evaluation and centralized policy management with proper caching and invalidation.

### Task 3: Performance Optimization - Search Indexing Pipeline Throughput

Optimize the search service's document indexing pipeline to achieve sub-minute search availability for newly created documents. Current implementation processes documents sequentially with blocking Elasticsearch calls. Implement parallel processing of independent documents, intelligent batching, backpressure handling, and priority queuing for recently accessed documents.

### Task 4: API Extension - Workspace Activity Audit Log API

Design and implement an Audit Log API that captures all security-relevant events across CloudMatrix services for SOC 2 and GDPR compliance. The API should support time-range queries, filtering by actor/resource/action type, and pagination for large result sets. Events must be tamper-evident with cryptographic chaining, and the system should support webhook forwarding to external SIEM systems.

### Task 5: Migration - PostgreSQL to Event-Sourced Document Store

Migrate the document storage layer from snapshot-based PostgreSQL storage to an event-sourced architecture where each edit operation is persisted as an immutable event. The event store should support efficient reconstruction of document state at any point in time, compaction strategies for storage efficiency, and streaming replay for real-time sync. Migration must be backwards compatible with a transition period supporting both systems.

## Getting Started

```bash
cd js/cloudmatrix
docker compose up -d
npm test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
