# EventHorizon - Alternative Tasks

## Overview

EventHorizon offers five alternative task types that test different software engineering disciplines beyond debugging. These tasks exercise feature development, refactoring, optimization, API extension, and migration on the same distributed event ticketing platform codebase.

## Environment

- **Language**: C# 12 / .NET 8
- **Infrastructure**: ASP.NET Core 8, EF Core 8, MassTransit 8, PostgreSQL, Redis, RabbitMQ, Consul
- **Difficulty**: Principal/Staff Engineer
- **Services**: 10+ microservices with shared library

## Tasks

### Task 1: Feature Development - Dynamic Pricing Engine (Feature)

Implement a dynamic pricing system that adjusts ticket prices based on real-time demand, time until event, and inventory levels. The system must support multiple pricing strategies (surge pricing, early-bird discounts, last-minute discounts), enforce minimum/maximum price bounds per event, handle concurrent price requests safely, and emit events through the EventBus for downstream services to react.

### Task 2: Refactoring - Extract Order Saga Orchestrator (Refactor)

Refactor the order processing logic to properly separate saga orchestration from domain logic. Extract saga step handlers into separate classes with explicit Execute and Compensate methods, implement a proper state machine, eliminate deadlock-prone lock patterns, ensure compensation runs in reverse order on failure, add saga state persistence, and integrate with the EventBus.

### Task 3: Performance Optimization - Search Service Caching Layer (Optimize)

Optimize the Search service performance by implementing a proper distributed caching layer with cache stampede prevention, appropriate TTL management, and intelligent cache invalidation. Implement a two-tier cache strategy (local + distributed), subscribe to event lifecycle events for cache invalidation, add cache hit/miss metrics, and reduce average search latency by at least 50% for repeated queries.

### Task 4: API Extension - Bulk Ticket Operations (API)

Extend the Tickets and Orders APIs to support bulk operations including batch reservations for group bookings, bulk transfers between customers, and mass cancellations. Implement all-or-nothing transactional semantics for bulk reservations, avoid N+1 query patterns, integrate with Notifications service for batch confirmations, add bulk-specific rate limiting, and provide detailed error responses.

### Task 5: Migration - Event Sourcing for Order Audit Trail (Migration)

Migrate the Orders service to use event sourcing for order aggregate persistence. Implement an event store for persisting ordered sequences of domain events, create a projection system for querying current state, ensure backward compatibility with existing orders, add an API endpoint for order history retrieval, integrate with the EventBus, and implement snapshotting for performance.

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run tests
dotnet test

# Or run in Docker
docker compose -f docker-compose.test.yml up --build
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). All existing tests continue to pass, new functionality is covered by unit tests, and the design properly integrates with existing services through the EventBus and dependency injection.
