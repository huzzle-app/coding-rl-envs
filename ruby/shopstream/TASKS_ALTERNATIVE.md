# ShopStream - Alternative Tasks

These alternative tasks provide different ways to engage with the ShopStream e-commerce platform codebase. Each task focuses on a specific type of software engineering work within the retail/e-commerce domain.

---

## Task 1: Feature Development - Multi-Warehouse Inventory Fulfillment

### Description

ShopStream currently treats all inventory as a single pool, but the business is expanding to support multiple warehouse locations across different regions. Customers should receive orders from the warehouse closest to their shipping address to minimize delivery time and shipping costs.

The fulfillment system needs to be enhanced to support warehouse-aware inventory management. When an order is placed, the system should determine the optimal warehouse(s) to fulfill the order based on stock availability, proximity to the customer, and shipping cost considerations. Orders may need to be split across multiple warehouses if no single location has complete inventory.

This feature requires changes to the inventory reservation system, order fulfillment workflow, and shipping cost calculations. The saga pattern used for order processing must be updated to handle partial fulfillment scenarios and compensation logic when a warehouse becomes unavailable mid-fulfillment.

### Acceptance Criteria

- Inventory records are associated with specific warehouse locations
- The reservation service selects optimal warehouse(s) based on shipping address proximity
- Orders can be split across multiple warehouses when necessary
- Shipping costs are calculated per-shipment based on origin warehouse
- The order saga handles multi-warehouse fulfillment with proper compensation
- Warehouse stock levels are updated atomically to prevent overselling
- API responses include warehouse origin information for each line item
- Background jobs handle warehouse inventory synchronization

### Test Command

```bash
bundle exec rspec spec/services/fulfillment_service_spec.rb spec/services/reservation_service_spec.rb spec/models/order_spec.rb
```

---

## Task 2: Refactoring - Extract Pricing Domain into Clean Architecture

### Description

The pricing logic in ShopStream is currently scattered across multiple services including `PricingService`, `DiscountService`, `TaxCalculator`, and parts of the `Order` model. This tight coupling makes it difficult to add new pricing rules, test discount combinations, and ensure financial accuracy across the platform.

Refactor the pricing domain into a clean architecture with clear boundaries. The pricing module should follow the hexagonal architecture pattern with domain entities (Price, Discount, Tax), use cases (CalculateOrderTotal, ApplyDiscount, ValidateCoupon), and adapters for external services (tax APIs, currency conversion). All monetary calculations should be isolated in a single module that enforces BigDecimal usage.

The refactored code should maintain backward compatibility with existing API contracts while enabling easier extension for future pricing features like tiered pricing, volume discounts, and dynamic pricing rules.

### Acceptance Criteria

- All pricing logic is consolidated into a dedicated pricing module
- Domain entities encapsulate business rules for discounts, taxes, and totals
- Use case classes handle orchestration of pricing calculations
- All monetary values use BigDecimal throughout the pricing pipeline
- External service calls (tax API, currency) go through adapter interfaces
- Existing API responses remain unchanged after refactoring
- Discount stacking rules are explicitly defined and enforced
- Unit tests cover all pricing calculation edge cases

### Test Command

```bash
bundle exec rspec spec/services/pricing_service_spec.rb spec/services/discount_service_spec.rb spec/services/tax_calculator_spec.rb
```

---

## Task 3: Performance Optimization - Product Catalog Search and Caching

### Description

The product catalog service is experiencing performance degradation during high-traffic periods, particularly during flash sales and promotional events. Database queries are slow, cache hit rates are low, and the search functionality times out under load. The catalog serves 50,000+ products with complex filtering by category, brand, price range, and availability.

Optimize the catalog service to handle 10x current traffic. This includes implementing efficient caching strategies that prevent cache stampedes, optimizing database queries with proper indexing, and improving the search service to handle complex filter combinations without N+1 queries or full table scans.

Special attention should be paid to cache invalidation patterns when products are updated, ensuring that stale data is not served to customers while avoiding excessive database load. The category tree navigation should be optimized for the common case of browsing hierarchical categories.

### Acceptance Criteria

- Product queries complete in under 50ms for 95th percentile
- Cache stampede protection prevents database overload on cache expiry
- Category tree queries use materialized paths or nested sets for efficiency
- Search filters use composite indexes covering common filter combinations
- Bulk product fetches use batch loading to eliminate N+1 queries
- Cache warming jobs pre-populate cache before promotional events
- Cache invalidation is targeted and does not cause cascading misses
- Memory usage for cached products is bounded with LRU eviction

### Test Command

```bash
bundle exec rspec spec/services/product_cache_spec.rb spec/services/filter_service_spec.rb spec/services/category_cache_spec.rb spec/services/search_service_spec.rb
```

---

## Task 4: API Extension - Subscription and Recurring Orders

### Description

ShopStream needs to support subscription-based purchasing where customers can set up recurring orders for consumable products (e.g., coffee, pet food, vitamins). Subscribers should receive a discount compared to one-time purchases, and the system must handle subscription lifecycle events including pause, resume, skip, and cancellation.

Design and implement the subscription API endpoints and background processing. Subscriptions have configurable frequencies (weekly, bi-weekly, monthly), payment methods that must be validated before each renewal, and inventory that must be reserved in advance to guarantee fulfillment. Failed renewals should trigger retry logic with customer notifications.

The subscription system must integrate with the existing order processing saga, payment service, and inventory management while maintaining clear separation of concerns. Webhook endpoints should notify external systems of subscription state changes.

### Acceptance Criteria

- REST API endpoints for subscription CRUD operations
- Support for multiple subscription frequencies with custom intervals
- Automatic order creation based on subscription schedule
- Payment method validation and pre-authorization before renewal
- Inventory pre-reservation for upcoming subscription orders
- Graceful handling of payment failures with configurable retry logic
- Customer notification events for subscription lifecycle changes
- Subscription discount applied automatically to recurring orders
- Webhook integration for external system notifications

### Test Command

```bash
bundle exec rspec spec/controllers/subscriptions_controller_spec.rb spec/services/subscription_service_spec.rb spec/jobs/subscription_renewal_job_spec.rb
```

---

## Task 5: Migration - Event Sourcing for Order History

### Description

The current order system uses traditional CRUD operations which makes it difficult to audit order changes, implement time-travel queries for customer support, and replay events for analytics. Migrate the order domain to an event-sourced architecture where all state changes are captured as immutable events.

The migration must be performed incrementally without downtime. Implement the event store, aggregate root pattern for orders, and projections that maintain the current read models. The system should support rebuilding order state from events and provide an audit trail showing who made changes and when.

Existing order data must be migrated to the event-sourced model by synthesizing creation events from current records. The Kafka event infrastructure should be leveraged for publishing domain events while the event store maintains the authoritative event log.

### Acceptance Criteria

- Event store persists all order state changes as immutable events
- Order aggregate root enforces business rules before emitting events
- Projections maintain current read models from event streams
- Historical order state can be reconstructed at any point in time
- Event replay capability supports analytics and debugging
- Migration script synthesizes events from existing order records
- Kafka integration publishes events for downstream consumers
- Event versioning handles schema evolution gracefully
- Zero downtime migration with dual-write during transition

### Test Command

```bash
bundle exec rspec spec/services/event_store_spec.rb spec/services/event_replay_service_spec.rb spec/models/order_spec.rb spec/consumers/payment_consumer_spec.rb
```
