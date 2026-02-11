# FleetPulse - Alternative Task Specifications

This document contains alternative task specifications for the FleetPulse fleet management platform. Each task represents a realistic engineering challenge that could be assigned to a Principal/Staff engineer.

---

## Task 1: Multi-Stop Route Optimization with Time Windows (Feature Development)

### Description

FleetPulse's enterprise customers are requesting support for time-windowed delivery scheduling. Currently, the route optimization service optimizes purely for distance, but real-world logistics require respecting delivery time windows (e.g., "deliver between 9 AM - 11 AM"). Customers with strict SLAs are churning because drivers arrive outside their required windows.

The feature must integrate with the existing dispatch service to provide optimized multi-stop routes that respect each waypoint's time window constraints. The optimizer should minimize total route distance while ensuring all time windows are satisfied. When time windows conflict (impossible to satisfy all), the system should return a partial solution with a list of violated constraints rather than failing entirely.

This feature will be used by the dispatch service to automatically generate driver assignments and by the analytics service to forecast on-time delivery rates. The billing service may also use time window data to apply SLA penalty credits.

### Acceptance Criteria

- Route optimization accepts time window constraints (earliest arrival, latest arrival) per waypoint
- Optimizer respects time windows while minimizing total distance traveled
- Routes that cannot satisfy all time windows return partial solutions with constraint violation details
- Time window calculations correctly handle timezone boundaries for cross-region deliveries
- Integration with dispatch service allows automatic driver assignment based on optimized routes
- Performance requirement: optimize routes with up to 50 waypoints in under 5 seconds
- API response includes estimated arrival times for each waypoint based on average speeds
- All existing route optimization tests continue to pass (backward compatibility)

### Test Command

```bash
mvn test
```

---

## Task 2: Consolidate Vehicle Telemetry Processing Pipeline (Refactoring)

### Description

The vehicle telemetry processing logic is currently scattered across multiple services: the tracking service handles GPS position updates, the vehicles service manages maintenance telemetry, and the compliance service processes Hours of Service (HOS) data. This fragmentation has led to code duplication, inconsistent event handling, and difficulty maintaining data consistency across services.

Engineering has identified that the same telemetry parsing and validation logic is duplicated in at least three places, with subtle differences that have caused production bugs. The Kafka consumers in each service also have slightly different error handling strategies, making it difficult to reason about message processing guarantees.

Refactor the telemetry processing into a unified pipeline in the shared module that all services can use. The refactored pipeline should provide consistent parsing, validation, and error handling while allowing each service to register its own processing handlers for service-specific logic.

### Acceptance Criteria

- Create a unified telemetry processing pipeline in the shared module
- All telemetry parsing and validation logic is consolidated (no duplication across services)
- Services register custom handlers for their specific telemetry processing needs
- Kafka consumer configuration is standardized across all telemetry-consuming services
- Error handling follows a consistent pattern with proper dead-letter queue support
- Existing service APIs remain unchanged (internal refactor only)
- All existing tests pass without modification
- New unit tests cover the shared telemetry pipeline with at least 80% coverage

### Test Command

```bash
mvn test
```

---

## Task 3: High-Frequency GPS Ingestion Optimization (Performance Optimization)

### Description

FleetPulse is experiencing performance degradation during peak hours when the tracking service processes GPS updates from 10,000+ active vehicles. Each vehicle sends position updates every 5 seconds, resulting in approximately 2,000 updates per second. Current P99 latency for position recording has climbed to 850ms, well above the 100ms SLA.

Profiling has identified several bottlenecks: the tracking service acquires write locks for every individual position update, blocking concurrent reads; the vehicle history is stored in a CopyOnWriteArrayList that becomes expensive with frequent writes; and each position triggers synchronous database writes and Kafka publishes.

The tracking service needs optimization to handle the current load with sub-100ms P99 latency while maintaining data consistency guarantees. The solution should also scale to support 50,000 concurrent vehicles as the business grows.

### Acceptance Criteria

- P99 latency for position recording under 100ms at 2,000 updates/second
- Position data remains consistent across reads and writes (no data loss or corruption)
- Batch processing for database writes to reduce connection pool pressure
- Asynchronous Kafka publishing with proper back-pressure handling
- Read operations are not blocked during write-heavy periods
- Memory usage remains stable under sustained load (no memory leaks)
- All existing tracking service tests pass
- New performance tests verify throughput and latency requirements

### Test Command

```bash
mvn test
```

---

## Task 4: Fuel Card Integration API (API Extension)

### Description

FleetPulse is partnering with major fuel card providers (Comdata, WEX, Fuelman) to offer integrated fuel expense tracking. Fleet managers want to see fuel transactions alongside vehicle tracking data, automatically match fuel purchases to specific trips, and detect potential fuel fraud (e.g., fueling when vehicle is 100 miles from station).

The integration requires extending the billing service with new REST endpoints for fuel card data ingestion and the analytics service with fuel efficiency reporting. Fuel transactions should be automatically correlated with tracking data to identify the trip and driver associated with each purchase. The system should flag suspicious transactions for review.

The API must support webhook-based real-time transaction notifications from fuel card providers and batch imports for historical data. Fuel costs should appear on invoices with proper categorization and the ability to bill back to specific customers or cost centers.

### Acceptance Criteria

- REST API endpoints for fuel card transaction ingestion (single and batch)
- Webhook endpoint for real-time transaction notifications with proper authentication
- Automatic trip-to-transaction matching based on GPS location and timestamp
- Fraud detection flags transactions where vehicle location is inconsistent with fuel station
- Fuel transactions appear as line items on customer invoices
- Analytics endpoints for fuel efficiency reporting (MPG by vehicle, driver, route)
- API documentation in OpenAPI 3.0 format
- All existing billing and analytics tests pass

### Test Command

```bash
mvn test
```

---

## Task 5: PostgreSQL to TimescaleDB Migration for Tracking Data (Migration)

### Description

The tracking service stores GPS position history in PostgreSQL, but query performance has degraded significantly as the table has grown to over 500 million rows. Time-range queries for historical position data now take 30+ seconds, making the fleet replay feature unusable. The operations team is also concerned about storage costs as the table grows by 50GB per month.

The team has decided to migrate tracking data to TimescaleDB (a PostgreSQL extension optimized for time-series data) to leverage automatic partitioning, compression, and time-based retention policies. The migration must be performed with zero downtime as the tracking service processes real-time GPS updates 24/7.

The migration plan should include a dual-write phase, data backfill for historical records, query migration to use TimescaleDB-specific optimizations, and a verification step to ensure data consistency. The system should support configurable retention policies (e.g., keep 90 days of full-resolution data, downsample older data).

### Acceptance Criteria

- Tracking data migrated to TimescaleDB hypertable with time-based partitioning
- Zero downtime during migration (dual-write pattern with gradual cutover)
- Historical data backfilled from PostgreSQL to TimescaleDB
- Compression enabled for data older than 7 days
- Configurable retention policy with automatic data expiration
- Time-range queries return results in under 500ms for 90-day ranges
- Downsampling continuous aggregate for data older than 90 days
- All existing tracking service tests pass with new storage layer
- Rollback procedure documented and tested

### Test Command

```bash
mvn test
```
