# CloudMatrix - Alternative Tasks

These alternative tasks provide different ways to engage with the CloudMatrix codebase beyond the primary debugging challenge. Each task focuses on a specific engineering discipline while maintaining the cloud services/SaaS platform domain context.

---

## Task 1: Feature Development - Usage-Based Billing with Metered Seats

### Description

CloudMatrix currently supports fixed subscription tiers (Basic, Pro, Enterprise) with static pricing. Product management has identified a significant customer segment that needs flexible, usage-based billing where costs scale with actual platform utilization rather than fixed seat counts.

Implement a metered billing system that tracks real-time usage across multiple dimensions: active document collaborators, storage consumption, API calls, and compute time for document processing. The system must support per-minute granularity for billing events, handle burst usage gracefully, and provide customers with real-time cost projections. Integration with the existing subscription service is required, allowing hybrid models where base subscriptions include bundled usage with overage charges.

The billing service must emit usage events to the analytics pipeline, support configurable rate cards per customer tier, and handle edge cases like free tier limits, usage caps, and billing cycle boundaries. Consider timezone-aware billing periods and proration for mid-cycle plan changes.

### Acceptance Criteria

- Metered billing tracks at least 4 usage dimensions (collaborators, storage, API calls, compute)
- Usage events are recorded with per-minute granularity minimum
- Real-time cost projection API returns estimated bill within 5% accuracy
- Hybrid billing model supports base subscription plus overage charges
- Rate cards are configurable per subscription tier
- Free tier enforces hard limits with graceful degradation
- Billing cycle boundary handling includes proration for plan changes
- All existing billing tests continue to pass

### Test Command

```bash
npm test
```

---

## Task 2: Refactoring - Extract Shared Permission Evaluation Engine

### Description

Permission checking logic is currently duplicated across multiple services: the gateway middleware validates JWT claims, the permissions service manages ACLs, the documents service checks edit permissions, and the presence service verifies collaboration access. Each implementation has subtle differences leading to inconsistent authorization behavior and security gaps.

Refactor the permission evaluation into a unified engine that all services consume. The engine should support a policy language that expresses rules for resource access, including inheritance hierarchies (organization > team > folder > document), role-based conditions, and attribute-based policies. The engine must be embeddable within each service for low-latency checks while also supporting centralized policy updates.

Consider the performance implications of permission checks in the hot path of real-time collaboration. The engine should support permission caching with proper invalidation when ACLs change, and must handle the eventual consistency of permission propagation across the distributed system.

### Acceptance Criteria

- Single permission evaluation engine replaces duplicated logic across services
- Policy language supports inheritance hierarchies (org > team > folder > document)
- Engine supports both embedded evaluation and centralized policy management
- Permission cache implements proper invalidation on ACL changes
- All existing permission-related tests pass without modification
- No new circular dependencies introduced
- Gateway, documents, presence, and permissions services use the shared engine
- Permission check latency does not regress for real-time collaboration paths

### Test Command

```bash
npm test
```

---

## Task 3: Performance Optimization - Search Indexing Pipeline Throughput

### Description

The search service's document indexing pipeline has become a bottleneck as customer document volumes have grown. Large enterprise customers report delays of 15-30 minutes between document creation and search availability. The current implementation processes documents sequentially, makes blocking Elasticsearch calls, and lacks batching optimizations.

Optimize the indexing pipeline to achieve sub-minute search availability for newly created documents while maintaining index consistency. The optimization should include parallel processing of independent documents, intelligent batching based on document size and cluster load, and backpressure handling when Elasticsearch is under stress. Consider implementing a priority queue where recently accessed documents are indexed first.

The solution must handle failure scenarios gracefully, including partial batch failures, Elasticsearch cluster unavailability, and document updates that arrive while indexing is in progress. Implement observability hooks that expose pipeline throughput, queue depth, and indexing latency percentiles.

### Acceptance Criteria

- Document indexing latency reduced to under 60 seconds for 95th percentile
- Pipeline supports parallel processing of at least 10 concurrent documents
- Intelligent batching groups small documents and splits large ones
- Backpressure mechanism prevents pipeline from overwhelming Elasticsearch
- Priority indexing available for recently accessed documents
- Partial batch failures do not block entire pipeline
- Observable metrics exposed for throughput, queue depth, and latency
- All existing search tests continue to pass

### Test Command

```bash
npm test
```

---

## Task 4: API Extension - Workspace Activity Audit Log API

### Description

Enterprise customers require comprehensive audit logging for compliance with SOC 2 and GDPR requirements. They need a queryable API that provides detailed records of all workspace activities including document access, permission changes, sharing events, and administrative actions. The current analytics service captures some events but lacks the retention guarantees and query capabilities needed for audit purposes.

Design and implement an Audit Log API that captures all security-relevant events across CloudMatrix services. The API should support time-range queries, filtering by actor/resource/action type, and pagination for large result sets. Events must be tamper-evident with cryptographic chaining to detect any modifications. Consider implementing log forwarding to customer SIEM systems via webhook integration.

The audit log must handle high event volumes without impacting the performance of primary operations. Implement appropriate data retention policies with configurable durations per customer tier, and ensure compliance with data residency requirements by supporting region-specific log storage.

### Acceptance Criteria

- Audit API captures events from all 15 CloudMatrix services
- Query API supports time-range, actor, resource, and action type filters
- Pagination handles result sets with 100k+ events efficiently
- Events include cryptographic chain for tamper detection
- Webhook integration enables forwarding to external SIEM systems
- Configurable retention policies support 90 days minimum for enterprise tier
- Event capture does not add more than 5ms latency to primary operations
- All existing tests continue to pass

### Test Command

```bash
npm test
```

---

## Task 5: Migration - PostgreSQL to Event-Sourced Document Store

### Description

CloudMatrix's document versioning system currently stores the full document content for each version in PostgreSQL. This approach consumes excessive storage for large documents with frequent saves, makes version comparison expensive, and loses the granular edit history needed for features like blame view and intelligent undo.

Migrate the document storage layer from snapshot-based PostgreSQL storage to an event-sourced architecture where each edit operation is persisted as an immutable event. The event store should support efficient reconstruction of document state at any point in time, compaction strategies for storage efficiency, and streaming replay for real-time sync.

The migration must be backwards compatible, supporting a transition period where both storage systems operate in parallel. Implement a migration tool that converts existing snapshot-based versions into event streams without data loss. Consider the implications for search indexing, which currently operates on full document snapshots.

### Acceptance Criteria

- Document edits persisted as immutable events rather than full snapshots
- Event store supports reconstruction of document state at any historical point
- Compaction strategy reduces storage for documents with 1000+ versions
- Migration tool converts existing snapshots to event streams
- Parallel operation mode supports gradual rollout with fallback capability
- Search indexing continues to function during and after migration
- Real-time collaboration sync integrates with event stream
- All existing document and versioning tests continue to pass

### Test Command

```bash
npm test
```
