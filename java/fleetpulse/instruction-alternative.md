# FleetPulse - Alternative Tasks

## Overview

Five alternative engineering challenges that test different skills on the FleetPulse fleet management platform. These tasks range from feature development and architectural refactoring to performance optimization, API integration, and complex database migrations.

## Environment

- **Language**: Java 21
- **Framework**: Spring Boot 3.2
- **Infrastructure**: Docker Compose with Kafka 3.6, PostgreSQL 15, Redis 7, Consul 1.17
- **Difficulty**: Principal (8-16 hours)

## Tasks

### Task 1: Multi-Stop Route Optimization with Time Windows (Feature Development)

Extend route optimization to support delivery time windows (e.g., "deliver between 9 AM - 11 AM"). Integrate with the dispatch service to automatically generate driver assignments while respecting time window constraints. Handle conflicting constraints by returning partial solutions with violation details. Requires timezone handling for cross-region deliveries and estimated arrival time calculations.

### Task 2: Consolidate Vehicle Telemetry Processing Pipeline (Refactoring)

Eliminate duplication across tracking, vehicles, and compliance services where telemetry parsing and validation logic is scattered. Create a unified pipeline in the shared module with consistent error handling and dead-letter queue support. Services register custom handlers for their specific needs while maintaining unchanged external APIs. Tests pass without modification.

### Task 3: High-Frequency GPS Ingestion Optimization (Performance Optimization)

Reduce P99 latency for position recording from 850ms to sub-100ms at 2,000 updates/second. Address bottlenecks: write lock contention, expensive CopyOnWriteArrayList, and synchronous database writes/Kafka publishes. Implement batch processing and asynchronous event publishing with backpressure handling. Support scaling to 50,000 concurrent vehicles.

### Task 4: Fuel Card Integration API (API Extension)

Extend billing and analytics services with REST endpoints for fuel card transaction ingestion from providers (Comdata, WEX, Fuelman). Implement webhook-based real-time notifications and batch imports. Automatically match fuel purchases to trips using GPS data. Flag suspicious transactions (vehicle location inconsistent with fuel station) for fraud detection. Include fuel costs on customer invoices.

### Task 5: PostgreSQL to TimescaleDB Migration for Tracking Data (Migration)

Migrate tracking position history (500M+ rows) from PostgreSQL to TimescaleDB for time-series optimization. Achieve zero downtime using dual-write pattern with gradual cutover. Enable compression for data older than 7 days and configurable retention policies. Reduce time-range query latency from 30+ seconds to under 500ms. Include rollback procedure and comprehensive testing.

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/java/fleetpulse

# Start infrastructure
docker compose up -d

# Run tests
mvn test -B
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
