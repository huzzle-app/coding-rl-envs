# EventHorizon - Alternative Tasks

These alternative tasks provide different ways to work with the EventHorizon event ticketing platform codebase. Each task focuses on a specific type of software engineering work.

---

## Task 1: Feature Development - Dynamic Pricing Engine

### Description

EventHorizon needs a dynamic pricing system that adjusts ticket prices based on real-time demand, time until the event, and current inventory levels. The pricing engine should integrate with the existing Tickets, Events, and Analytics services to gather the necessary data for pricing decisions.

The system should support multiple pricing strategies including surge pricing during high-demand periods, early-bird discounts for tickets purchased well in advance, and last-minute discounts for events with low sell-through rates. Pricing rules should be configurable per event and venue, allowing event organizers to set minimum and maximum price bounds.

The pricing calculations must maintain accuracy for financial transactions, properly handle concurrent price requests during flash sales, and emit events through the EventBus when prices change so that downstream services (Notifications, Search) can react accordingly.

### Acceptance Criteria

- Implement a pricing service that calculates dynamic prices based on demand ratio (sold/capacity), days until event, and historical sales velocity
- Support at least three pricing strategies: SurgePricing, EarlyBird, and LastMinuteDiscount with configurable thresholds
- Ensure price calculations use appropriate numeric types for currency to avoid precision loss in financial calculations
- Integrate with the existing TicketInventoryService to retrieve real-time availability data
- Publish price change events through the EventBus that include event ID, old price, new price, and reason for change
- Enforce minimum and maximum price bounds per event to prevent prices from going outside acceptable ranges
- Handle concurrent pricing requests safely during high-traffic scenarios without race conditions
- All existing tests continue to pass and new functionality is covered by unit tests

### Test Command

```bash
dotnet test
```

---

## Task 2: Refactoring - Extract Order Saga Orchestrator

### Description

The current order processing logic in the Orders service mixes saga orchestration with domain logic, making it difficult to test, extend, and reason about failure scenarios. The OrderSagaService handles both the saga state machine and the compensation logic in an ad-hoc manner with manual lock management.

Refactor the order processing flow to use a proper saga orchestrator pattern that clearly separates the saga state machine from individual step handlers. Each step in the order saga (reserve tickets, process payment, send confirmation, update analytics) should be encapsulated in its own handler with explicit success and compensation logic.

The refactored design should eliminate the current deadlock-prone lock acquisition patterns, properly handle partial failures during multi-step transactions, and provide clear visibility into the current state of any order through its saga state. The orchestrator should integrate with the existing EventBus for inter-service communication.

### Acceptance Criteria

- Extract saga step handlers into separate classes with explicit Execute and Compensate methods
- Implement a saga state machine that tracks order progress through defined states: Created, TicketsReserved, PaymentProcessed, Confirmed, and compensating states
- Remove direct lock management from saga logic and replace with a consistent resource acquisition strategy
- Ensure compensation runs in reverse order of execution when any step fails
- Add saga state persistence so orders can resume after service restart
- Emit saga lifecycle events (SagaStarted, StepCompleted, StepFailed, SagaCompleted, SagaCompensated) through the EventBus
- Maintain backward compatibility with existing OrderController endpoints
- All existing tests pass and saga state transitions are covered by new tests

### Test Command

```bash
dotnet test
```

---

## Task 3: Performance Optimization - Search Service Caching Layer

### Description

The Search service is experiencing performance issues during peak traffic, particularly when users perform repeated searches for popular events. The current implementation has no effective caching strategy, and the DistributedSearchCache has race conditions that cause cache stampedes where multiple threads simultaneously compute the same expensive search results.

Optimize the Search service by implementing a proper distributed caching layer with cache stampede prevention, appropriate TTL management, and cache invalidation when event data changes. The solution should handle the case where cached search results become stale when events are updated, cancelled, or sell out.

Consider the interaction between the local in-memory cache and the distributed cache layer. The system should provide fast responses for cache hits while ensuring consistency guarantees are appropriate for a search use case (eventual consistency is acceptable, but stale data should not persist indefinitely).

### Acceptance Criteria

- Implement cache stampede prevention so only one thread computes cache entries while others wait
- Add proper TTL configuration with different expiry times for different query types (popular events vs. specific searches)
- Implement cache invalidation that subscribes to event lifecycle events (EventUpdated, EventCancelled, TicketsSoldOut) via the EventBus
- Add a two-tier caching strategy with local in-memory cache backed by distributed cache
- Ensure ValueTask-returning methods are consumed correctly without undefined behavior from multiple awaits
- Add cache hit/miss metrics that can be exposed through the Analytics service
- Reduce average search latency by at least 50% for repeated queries as measured by tests
- All existing tests pass and caching behavior is covered by new tests

### Test Command

```bash
dotnet test
```

---

## Task 4: API Extension - Bulk Ticket Operations

### Description

Large event organizers have requested the ability to perform bulk operations on tickets, including batch reservations for group bookings, bulk transfers between customers, and mass cancellations for event date changes. The current API only supports single-ticket operations, forcing clients to make hundreds of individual requests for large transactions.

Extend the Tickets and Orders APIs to support bulk operations with proper transactional semantics. A bulk reservation should either reserve all requested tickets or none (all-or-nothing), with appropriate error reporting when partial fulfillment is not possible. The bulk endpoints should be efficient, avoiding N+1 query patterns when processing large batches.

The implementation should consider rate limiting for bulk endpoints to prevent abuse, proper authentication to ensure only authorized users can perform bulk operations, and integration with the Notifications service to send batch confirmations rather than individual notifications per ticket.

### Acceptance Criteria

- Add POST /api/tickets/bulk-reserve endpoint accepting a list of ticket IDs and customer information
- Add POST /api/tickets/bulk-transfer endpoint for transferring multiple tickets between customers in a single transaction
- Add POST /api/tickets/bulk-cancel endpoint for mass cancellation with refund coordination
- Implement all-or-nothing transactional semantics for bulk reservations with proper rollback on partial failure
- Return detailed error responses indicating which specific tickets failed and why
- Batch database operations to avoid N+1 query patterns during bulk processing
- Integrate with NotificationService to send consolidated notification for bulk operations rather than per-ticket notifications
- Implement bulk-specific rate limiting (lower request limit but allowing larger payloads)
- All existing tests pass and bulk operations are covered by new tests

### Test Command

```bash
dotnet test
```

---

## Task 5: Migration - Event Sourcing for Order Audit Trail

### Description

Regulatory requirements mandate that EventHorizon maintain a complete audit trail of all order state changes for compliance and dispute resolution. The current implementation uses mutable state that overwrites previous values, losing the history of how orders evolved over time.

Migrate the Orders service to use event sourcing for order aggregate persistence. Instead of storing current state, store the sequence of events that led to the current state (OrderCreated, TicketsAdded, PaymentReceived, OrderConfirmed, RefundRequested, etc.). The current state should be derived by replaying these events.

The migration must be backward compatible, meaning existing orders created before the migration should continue to work. Implement a projection system that materializes the current order state for efficient querying, while the event store maintains the complete history. The event store should integrate with the existing EventBus for publishing domain events to other services.

### Acceptance Criteria

- Implement an event store abstraction for persisting and retrieving order events in sequence
- Define domain events for all order state transitions: OrderCreated, TicketsReserved, PaymentProcessed, OrderConfirmed, RefundRequested, RefundCompleted, OrderCancelled
- Implement order aggregate that rebuilds current state by replaying stored events
- Create a projection that maintains a queryable current-state view updated as events are appended
- Ensure existing orders (created before migration) continue to function through a compatibility layer
- Add API endpoint GET /api/orders/{id}/history returning the complete event history for an order
- Integrate event publishing with the EventBus so other services receive order domain events
- Implement snapshotting for orders with many events to optimize replay performance
- All existing tests pass and event sourcing behavior is covered by new tests

### Test Command

```bash
dotnet test
```
