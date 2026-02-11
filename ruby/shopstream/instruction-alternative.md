# ShopStream - Alternative Tasks

## Overview

ShopStream supports five alternative task types beyond debugging: multi-warehouse inventory fulfillment, pricing domain refactoring, catalog search optimization, subscription/recurring order support, and event sourcing migration for order history. Each task deepens your understanding of the e-commerce platform's architecture while exercising different software engineering skills.

## Environment

- **Language**: Ruby on Rails
- **Infrastructure**: Kafka, PostgreSQL, Redis, Elasticsearch (10 microservices)
- **Difficulty**: Principal Engineer (8-16 hours)

## Tasks

### Task 1: Feature Development - Multi-Warehouse Inventory Fulfillment

Enhance ShopStream's fulfillment system to support multiple warehouse locations. When orders are placed, the system should select optimal warehouse(s) based on stock availability and proximity to customer shipping addresses. Orders may be split across multiple warehouses if no single location has complete inventory. The saga pattern for order processing must be updated to handle partial fulfillment scenarios and compensation logic.

**Key Requirements**: Inventory location association, proximity-based warehouse selection, multi-warehouse order splitting, per-shipment shipping cost calculation, saga updates for partial fulfillment, atomic inventory updates, warehouse origin in API responses, background job synchronization.

### Task 2: Refactoring - Extract Pricing Domain into Clean Architecture

Consolidate scattered pricing logic (PricingService, DiscountService, TaxCalculator, Order model) into a clean, hexagonal architecture with clear domain boundaries. The pricing module should include domain entities (Price, Discount, Tax), use cases (CalculateOrderTotal, ApplyDiscount, ValidateCoupon), and adapters for external services. All monetary calculations must use BigDecimal to ensure financial accuracy.

**Key Requirements**: Pricing module consolidation, domain entity encapsulation, use case orchestration, BigDecimal enforcement, adapter interfaces for external services, backward-compatible API contracts, explicit discount stacking rules, comprehensive unit tests.

### Task 3: Performance Optimization - Product Catalog Search and Caching

Optimize the catalog service to handle 10x current traffic during flash sales and promotional events. Implement efficient caching strategies preventing cache stampedes, optimize database queries with proper indexing, and improve the search service to eliminate N+1 queries and full table scans. Cache invalidation patterns must prevent stale data while avoiding excessive database load.

**Key Requirements**: Sub-50ms query performance (95th percentile), cache stampede protection, optimized category tree navigation, composite indexes for common filters, batch loading elimination of N+1 queries, pre-event cache warming, targeted invalidation, bounded memory with LRU eviction.

### Task 4: API Extension - Subscription and Recurring Orders

Design and implement subscription-based purchasing for recurring orders. Customers can set up recurring orders for consumables with configurable frequencies (weekly, bi-weekly, monthly) at discounted rates. The system must handle subscription lifecycle events (pause, resume, skip, cancel), validate payment methods before renewals, reserve inventory in advance, and provide customer notifications for state changes.

**Key Requirements**: REST API endpoints for subscription CRUD, multiple frequency support, automatic order creation per schedule, payment method validation, inventory pre-reservation, graceful failure handling with retries, lifecycle notifications, automatic discounting, webhook integration.

### Task 5: Migration - Event Sourcing for Order History

Migrate the order domain to event-sourced architecture where all state changes are captured as immutable events. Enable auditing, time-travel queries for support, and event replay for analytics. The migration must be incremental without downtime using dual-write during transition. Existing order data must be migrated by synthesizing creation events.

**Key Requirements**: Immutable event store, order aggregate root with business rules, projections for read models, historical state reconstruction, event replay capability, migration script with event synthesis, Kafka integration, graceful schema evolution, zero-downtime dual-write migration.

## Getting Started

```bash
# Start all services
docker compose up -d

# Set up databases for all services
docker compose exec gateway rails db:create db:migrate db:seed
docker compose exec auth rails db:create db:migrate db:seed
docker compose exec catalog rails db:create db:migrate db:seed
docker compose exec inventory rails db:create db:migrate db:seed
docker compose exec orders rails db:create db:migrate db:seed
docker compose exec payments rails db:create db:migrate db:seed
docker compose exec shipping rails db:create db:migrate db:seed
docker compose exec search rails db:create db:migrate db:seed
docker compose exec notifications rails db:create db:migrate db:seed
docker compose exec analytics rails db:create db:migrate db:seed

# Run tests
bundle exec rspec
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) for your selected task, including all unit tests, integration tests, and edge case coverage specified therein.
