# VertexGrid - Alternative Task Specifications

This document describes alternative tasks for the VertexGrid grid analytics and vehicle management platform. Each task represents a realistic engineering scenario that exercises multiple modules across the codebase.

---

## Task 1: Real-Time Fleet Geofencing Alerts (Feature Development)

### Description

VertexGrid customers are requesting a real-time geofencing alerting system that notifies dispatchers when vehicles enter or exit predefined geographic boundaries. The system must integrate with the existing tracking infrastructure to monitor vehicle positions and trigger alerts when boundary crossings occur.

The feature needs to support multiple geofence types including circular zones (defined by center point and radius), polygonal boundaries (for irregular service areas), and corridor zones (for route adherence monitoring). Alerts must be delivered through the existing notification service with configurable delivery channels (push, SMS, webhook) per geofence.

Performance is critical since the system processes high-frequency GPS updates from thousands of vehicles. The geofence evaluation must be efficient enough to handle position updates every 5 seconds per vehicle without introducing latency into the tracking pipeline. Historical geofence events should be stored for compliance reporting and analytics dashboards.

### Acceptance Criteria

- Geofence definitions support circular, polygonal, and corridor boundary types with configurable entry/exit triggers
- Position updates from TrackingService trigger geofence evaluation within 100ms processing time
- Alert delivery integrates with NotificationService supporting at-least-once delivery semantics
- Geofence events are persisted with vehicle ID, geofence ID, event type (ENTER/EXIT), and timestamp
- Analytics dashboard can query geofence violations by vehicle, time range, and zone type
- Bulk geofence import supports GeoJSON format for enterprise customers
- Rate limiting prevents alert storms when vehicles oscillate near boundaries
- Geofence evaluation uses spatial indexing to handle 10,000+ active geofences efficiently

### Test Command

```bash
mvn test
```

---

## Task 2: Invoice Service Monetary Calculation Refactoring (Refactoring)

### Description

The billing module currently uses a mix of `double`, `float`, and `BigDecimal` types for monetary calculations, leading to precision errors that have caused revenue discrepancies in production. A comprehensive refactoring effort is needed to standardize all financial calculations on `BigDecimal` with explicit scale and rounding modes.

The refactoring scope includes the InvoiceService, PaymentService, and all related models. Every monetary field must use `BigDecimal` with 2-decimal precision for currency amounts and 6-decimal precision for unit rates. Division operations must specify `RoundingMode.HALF_UP` to match standard accounting practices.

Additionally, the current approach to accumulating totals across collections uses patterns that lose precision over many iterations. These accumulation patterns need to be replaced with stream-based reduction using `BigDecimal::add` to maintain precision regardless of collection size. The geographic billing zone calculation also requires higher precision to avoid misclassifying boundary customers.

### Acceptance Criteria

- All monetary fields in Invoice and InvoiceItem models use `BigDecimal` with explicit scale
- InvoiceService calculations use `BigDecimal` throughout with no intermediate `double` conversions
- Division operations specify `RoundingMode.HALF_UP` and handle zero divisor cases gracefully
- Revenue accumulation across invoice collections maintains cent-level precision for 100,000+ invoices
- Geographic coordinate precision increased to 6 decimal places for billing zone determination
- Tax calculation returns `BigDecimal` with 2-decimal scale matching invoice currency precision
- Unit tests verify precision is maintained when processing invoices with sub-cent unit prices
- Backward compatibility maintained for existing invoice records with `double` serialization

### Test Command

```bash
mvn test
```

---

## Task 3: Tracking Telemetry Pipeline Performance Optimization (Performance Optimization)

### Description

The tracking module processes GPS telemetry from fleet vehicles but experiences performance degradation during peak hours when update frequency increases. Profiling has identified several bottlenecks: nested parallel stream operations causing ForkJoinPool contention, inefficient distance calculations using repeated trigonometric functions, and lock contention on the read-write lock protecting position state.

The optimization effort should address the parallel stream deadlock potential by restructuring the vehicle speed calculation pipeline. The Haversine distance calculation is invoked thousands of times per second and should be optimized with caching for common coordinate pairs and early-exit for nearby points that can use planar approximation.

The read-write lock implementation needs tuning for the read-heavy workload pattern where position queries outnumber updates 100:1. Consider lock striping or lock-free data structures where appropriate. Additionally, the integer overflow risk in total distance calculation should be addressed as part of this optimization work.

### Acceptance Criteria

- Vehicle speed calculation avoids nested parallel streams to prevent ForkJoinPool thread starvation
- Distance calculation supports planar approximation for points within 10km to reduce computation
- Read-write lock implementation uses fair ordering to prevent reader starvation under high write load
- Total distance calculation uses `long` to prevent integer overflow for continental-scale routes
- Position update throughput handles 50,000 updates per second on reference hardware
- Memory allocation reduced by 40% through object pooling for TrackingData instances
- Latency p99 for position queries remains under 5ms during peak telemetry ingestion
- Stream collector operations handle duplicate vehicle IDs gracefully without exceptions

### Test Command

```bash
mvn test
```

---

## Task 4: Fleet Management REST API v2 Extension (API Extension)

### Description

VertexGrid needs to expose a v2 REST API that consolidates vehicle, dispatch, and tracking operations into a unified fleet management interface. The new API version introduces composite endpoints that reduce client round-trips by combining data from multiple services in single responses.

The v2 API must support a unified fleet status endpoint that returns vehicle details, current position, active dispatch assignments, and compliance status in a single call. Pagination must be cursor-based rather than offset-based to handle real-time fleet changes without skipping or duplicating results. The API should support field selection to allow clients to request only the data they need.

Batch operations are required for enterprise integrations: bulk vehicle status updates, mass reassignment of dispatch jobs, and fleet-wide compliance checks. These batch endpoints must be transactional with all-or-nothing semantics and provide detailed error reporting for partial failures.

### Acceptance Criteria

- Fleet status endpoint aggregates vehicle, position, dispatch, and compliance data with sub-200ms response time
- Cursor-based pagination maintains consistency when fleet vehicles change during traversal
- Field selection via query parameter reduces payload size by excluding unrequested nested objects
- Batch vehicle update endpoint processes up to 1,000 vehicles transactionally with rollback on failure
- Batch dispatch reassignment validates driver availability and HOS compliance before committing
- API versioning uses URL path prefix (`/api/v2/`) with v1 endpoints remaining unchanged
- Rate limiting applied per-client with configurable quotas stored in gateway configuration
- OpenAPI 3.0 specification generated automatically from controller annotations

### Test Command

```bash
mvn test
```

---

## Task 5: Legacy Dispatch Assignment Migration (Migration)

### Description

The dispatch module currently stores job assignments using an in-memory `ConcurrentHashMap` which loses state on service restart. The migration effort will move assignment persistence to a durable data store while maintaining the high-throughput requirements of the real-time dispatch system.

The migration must be performed with zero downtime using a dual-write strategy: new assignments are written to both the legacy in-memory store and the new persistent store, while reads gradually shift to the persistent store after validation. A reconciliation process must detect and resolve any divergence between the two stores.

Assignment history needs to be preserved for analytics and audit purposes. The new schema should support efficient queries by vehicle, driver, time range, and job status. The migration should also address the current prototype-scoped bean issue where NotificationDispatcher instances are not properly managed within the dispatch transaction boundaries.

### Acceptance Criteria

- Assignment persistence survives service restarts with less than 1 second of data loss window
- Dual-write mode allows gradual migration with instant rollback capability
- Reconciliation job runs every 5 minutes and logs any divergence between stores
- Assignment queries by vehicle or driver return results within 50ms for 30-day lookups
- Database schema supports assignment status transitions with audit timestamps
- NotificationDispatcher lifecycle properly managed within dispatch transaction scope
- Async job notification uses proper exception handling with logged failures
- Legacy in-memory store can be disabled via configuration after migration validation

### Test Command

```bash
mvn test
```
