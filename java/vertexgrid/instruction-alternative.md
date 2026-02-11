# VertexGrid - Alternative Tasks

## Overview
Five alternative task scenarios that test different software engineering skills: feature development, refactoring, performance optimization, API design, and system migration.

## Environment
- **Language**: Java
- **Infrastructure**: Spring Boot microservices with JPA/Hibernate, distributed state management, concurrent collections
- **Difficulty**: Apex-Principal
- **Estimated Hours**: 120-168 hours (5-7 days)

## Tasks

### Task 1: Real-Time Fleet Geofencing Alerts (Feature Development)
Implement a comprehensive geofencing alerting system for vehicle fleet management. The system must integrate with existing tracking infrastructure to detect when vehicles enter or exit predefined geographic boundaries, triggering notifications through multiple channels. Support circular zones, polygonal boundaries, and corridor zones. Geofence evaluation must process position updates in under 100ms using spatial indexing for 10,000+ active geofences. Store historical events for compliance reporting and handle rate-limiting to prevent alert storms.

### Task 2: Invoice Service Monetary Calculation Refactoring (Refactoring)
Standardize all financial calculations in the billing module to use `BigDecimal` with explicit scale and rounding modes. Eliminate inconsistent use of `double`, `float`, and `BigDecimal` that causes revenue discrepancies. Refactor InvoiceService, PaymentService, and related models to use 2-decimal precision for currency amounts and 6-decimal precision for unit rates. Replace accumulation patterns with stream-based reduction to maintain precision across large invoice collections.

### Task 3: Tracking Telemetry Pipeline Performance Optimization (Performance Optimization)
Optimize the tracking module's GPS telemetry processing during peak hours. Eliminate nested parallel stream operations causing ForkJoinPool contention. Optimize the Haversine distance calculation through caching and planar approximation for nearby points. Tune read-write locks for read-heavy workloads (100:1 read-to-write ratio). Handle integer overflow in total distance calculation and achieve 50,000 updates per second throughput while maintaining sub-5ms p99 latency for position queries.

### Task 4: Fleet Management REST API v2 Extension (API Extension)
Design and implement a v2 REST API that consolidates vehicle, dispatch, and tracking operations into a unified fleet management interface. Create composite endpoints reducing client round-trips by combining data from multiple services. Implement cursor-based pagination for consistency with real-time fleet changes and field selection to optimize payload size. Support batch operations with transactional semantics: bulk vehicle updates, mass dispatch reassignment, and fleet-wide compliance checks with detailed error reporting.

### Task 5: Legacy Dispatch Assignment Migration (Migration)
Migrate dispatch assignment persistence from in-memory `ConcurrentHashMap` to a durable data store while maintaining zero downtime. Implement dual-write strategy with gradual cutover from old to new store. Create reconciliation job detecting and resolving divergence. Preserve assignment history for audit purposes. Properly manage NotificationDispatcher lifecycle within dispatch transaction boundaries. Support rollback capability and enable legacy store disabling after validation.

## Getting Started

```bash
mvn test
```

Runs the full test suite. Currently passes ~0.5-5% of tests (1250+ bugs across 12,000+ stress scenarios).

## Success Criteria

Implementation of any task meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). Select one task to complete:

- **Task 1**: Geofence system with spatial indexing, alert delivery, and event persistence
- **Task 2**: BigDecimal-based billing with consistent precision across all modules
- **Task 3**: Optimized tracking pipeline with reduced latency and increased throughput
- **Task 4**: Functional v2 API with composite endpoints, pagination, and batch operations
- **Task 5**: Durable dispatch assignment persistence with dual-write and reconciliation

Each task can be pursued independently while using the shared codebase.
