# ShopStream - Greenfield Development Tasks

## Overview

ShopStream supports three greenfield implementation tasks that require building new microservices from scratch using existing architectural patterns. Each service must follow the hexagonal architecture, integrate with Kafka for event streaming, use BigDecimal for financial calculations, and achieve 95%+ test coverage.

## Environment

- **Language**: Ruby on Rails
- **Infrastructure**: Kafka, PostgreSQL, Redis (10+ microservices)
- **Difficulty**: Principal Engineer (8-16 hours per task)

## Tasks

### Task 1: Product Recommendation Engine

Implement a recommendation service providing personalized product suggestions based on user behavior, purchase history, and product relationships. The service must support multiple recommendation strategies (collaborative filtering, content-based, hybrid), track user interactions, prevent cache stampedes, and publish domain events for downstream consumers.

**Interface**: `RecommendationEngine` class with methods:
- `get_recommendations(limit: 10, strategy: :hybrid, exclude_purchased: true)` - Returns ranked `RecommendationResult` objects with confidence scores
- `frequently_bought_together(product_id:, limit: 5)` - Products commonly purchased with reference product
- `similar_products(product_id:, limit: 10)` - Products ranked by similarity to reference
- `record_interaction(product_id:, interaction_type:, metadata: {})` - Track user behavior (:view, :cart_add, :purchase, :wishlist)
- `invalidate_cache!` - Clear cached recommendations for user

**Key Components**: `UserInteraction` and `ProductSimilarity` models, `BehaviorProcessor` for batch event processing, background jobs for similarity calculation and co-occurrence updates, Kafka consumers for order/view/cart/wishlist events, Redis caching with TTL.

**Success Criteria**: 40+ unit specs, 15+ integration specs, 5+ concurrency specs, sub-100ms cached recommendations, sub-500ms uncached, 10,000+ events/minute throughput.

### Task 2: Gift Card Service

Implement a gift card system supporting purchase, redemption, balance management, transfers, and multi-currency support. The service must prevent double-spending through distributed locks, track all transactions for audit purposes, handle refunds to gift cards, and provide webhook integration for external systems.

**Interface**: `GiftCardService` class with methods:
- `create(amount:, currency: 'USD', purchaser_id:, recipient_email: nil, message: nil, expires_at: nil)` - Returns `GiftCard` with unique code
- `redeem(code:, order_id:, amount: nil)` - Applies to order, returns `RedemptionResult` with balance tracking
- `check_balance(code:)` - Returns `BalanceResult` (original, current, status, expiration)
- `refund_to_card(redemption_id:, amount: nil)` - Returns `RefundResult` with updated balance
- `transfer(from_code:, to_code:, amount:)` - Returns `TransferResult` with both new balances
- `void(code:, reason:, admin_id:)` - Cancel card (admin only)
- `bulk_create(count:, amount:, currency: 'USD', prefix: 'PROMO', expires_at: nil)` - Generate promotional cards

**Key Components**: `GiftCard`, `GiftCardTransaction` models with statuses (active, partially_redeemed, fully_redeemed, expired, voided), `CodeGenerator` for unique secure codes with checksums, `LockService` for atomic redemption, Kafka publishing for events.

**Success Criteria**: 50+ unit specs, 20+ integration specs, 10+ concurrency specs, 10+ financial precision specs, 5+ security specs, no floating-point errors, timing-safe code comparison, rate-limited balance checks.

### Task 3: Returns Processing System

Implement a returns management system handling return requests, approvals, refund processing, and inventory restocking. The service must enforce return windows per product category, calculate refunds with restocking fees and condition adjustments, integrate with payment/inventory services, and maintain complete audit trails.

**Interface**: `ReturnsService` class with methods:
- `initiate(order_id:, items:, reason:, description: nil, images: [])` - Create return request with `:defective, :wrong_item, :not_as_described, :no_longer_needed, :other` reasons
- `approve(return_id:, refund_method:, refund_amount: nil, restocking_fee: 0, notes: nil, approver_id:)` - Approve with refund method (`:original_payment, :store_credit, :gift_card, :exchange`), returns `ApprovalResult` with shipping label
- `reject(return_id:, reason:, rejector_id:)` - Deny return with audit trail
- `receive_items(return_id:, items_received:, receiver_id:)` - Record warehouse receipt with condition assessment (`:sellable, :damaged, :unsellable`)
- `complete(return_id:, final_refund_amount: nil)` - Process refund, returns `CompletionResult` with transaction details
- `check_eligibility(order_id:)` - Returns `EligibilityResult` showing returnable items and window expiry

**Key Components**: `ReturnRequest`, `ReturnItem`, `ReturnAuditLog` models with AASM state machine (pending → approved → shipped → received → completed/rejected/cancelled), `RefundCalculator` with condition adjustments, `PolicyEngine` with category-specific rules and windows, compensation saga for failures.

**Success Criteria**: 60+ unit specs, 25+ integration specs, 15+ policy specs, 10+ saga/compensation specs, 10+ financial precision specs, 5+ audit/compliance specs, complete audit trails, immutable history, proper actor tracking.

## General Requirements for All Tasks

### Architectural Patterns

All implementations must follow existing ShopStream patterns:

1. **Service Classes**: Business logic in `app/services/`, thin models with validations
2. **Result Objects**: Return structured results (e.g., `RecommendationResult`, `RedemptionResult`), not primitives
3. **Custom Exceptions**: Define in `app/errors/` with descriptive names
4. **YARD Documentation**: All public methods fully documented with `@param`, `@return`, `@raise`
5. **Frozen String Literals**: Add `# frozen_string_literal: true` to all files
6. **BigDecimal for Money**: Never use Float for financial/precision calculations
7. **Kafka Events**: Use `KafkaProducer.publish` for outbound events
8. **Redis Caching**: Use for performance-critical and recommendation data
9. **Distributed Locks**: Use `LockService` pattern for critical sections (redemption, transfers)
10. **State Machines**: Use AASM gem for lifecycle workflows

### Testing Standards

- **RSpec with FactoryBot** for fixtures and test setup
- **95%+ line coverage** across all specs
- **Request specs** for API endpoints
- **Mock external services** (Kafka, Redis, external APIs) in unit tests
- **Integration tests** with real services (Docker containers)
- **Edge case testing** for boundary conditions, concurrency, failures
- **Performance tests** for slow operations
- **Security tests** for auth, injection, timing attacks

### Service Directory Structure

```
services/[service_name]/
  app/
    controllers/
      api/
        v1/
          [resource]_controller.rb
    models/
      [model].rb
    services/
      [service].rb
    jobs/
      [job].rb
    consumers/
      [event]_consumer.rb
    errors/
      [error].rb
  config/
    routes.rb
    sidekiq.yml
  db/
    migrate/
  spec/
    models/
    services/
    controllers/
    jobs/
    consumers/
    factories/
    rails_helper.rb
  Gemfile
```

### Kafka Integration

- Subscribe to domain events from other services
- Publish domain events from your service
- Implement idempotent event handlers (check idempotency keys)
- Use event versioning for schema evolution
- Dead letter queue for failed events

## Getting Started

```bash
# Start all services
docker compose up -d

# Set up databases for all services (if not already done)
docker compose exec gateway rails db:create db:migrate db:seed
# ... repeat for all other services ...

# Generate new service scaffolding
rails new services/[service_name] --skip-test

# Run tests for all services
bundle exec rspec
```

## Success Criteria

Implementations pass all acceptance criteria from [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md):
- All unit, integration, concurrency, and specialized (financial/security/policy) tests pass
- Code follows existing service patterns and conventions
- Full YARD documentation with examples
- Kafka events published and consumed correctly
- Redis caching working without stampedes
- No BigDecimal floating-point issues
- Distributed locks preventing race conditions
- Audit trails and state machines for complex workflows
