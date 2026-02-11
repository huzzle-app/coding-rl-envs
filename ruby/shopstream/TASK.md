# ShopStream - E-Commerce Microservices Platform

## Task Description

You are debugging a distributed e-commerce platform built with Ruby on Rails microservices. The platform handles product catalog, inventory management, order processing, payments, shipping, and analytics.

## Known Issues

Tests are failing in several areas. Previous maintainer noted problems with async operations and data handling.

The codebase contains issues across 10 microservices that need to be identified and fixed. All 300+ tests must pass before the task is complete.

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

# Run all tests
./scripts/run_all_tests.sh

# Run tests for a specific service
docker compose exec orders bundle exec rspec
```

## Architecture

ShopStream is a microservices platform with 10 Ruby on Rails API services:

| Service | Port | Purpose |
| Gateway | 8000 | API Gateway, routing, rate limiting |
| Auth | 8001 | Authentication, sessions, API keys |
| Catalog | 8002 | Product catalog, categories |
| Inventory | 8003 | Stock management, reservations |
| Orders | 8004 | Order management, state machine |
| Payments | 8005 | Payment processing, refunds |
| Shipping | 8006 | Shipping calculation, tracking |
| Search | 8007 | Product search (Elasticsearch) |
| Notifications | 8008 | Email, SMS, push notifications |
| Analytics | 8009 | Event tracking, reporting |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| PostgreSQL 15 | Primary databases (per service) |
| Redis 7 | Caching, sessions, Sidekiq queues |
| Kafka | Event streaming between services |
| Elasticsearch | Product search |
| Mailhog | Email testing |

### Event-Driven Communication

Services communicate via Kafka events:
- `order.created` - New order placed
- `order.paid` - Payment confirmed
- `order.shipped` - Order shipped
- `inventory.reserved` - Stock reserved
- `inventory.released` - Stock released
- `payment.processed` - Payment completed
- `payment.refunded` - Refund issued

## Key Files by Service

### Gateway Service

### Auth Service

### Catalog Service

### Inventory Service

### Orders Service

### Payments Service

### Shipping Service

### Search Service

### Notifications Service

### Analytics Service

### Shared Library

## Test Categories

| Category | Tests | Focus |
| Unit | 120 | Model validations, service methods |
| Integration | 80 | API endpoints, service interactions |
| Consumer | 30 | Kafka event handling |
| Performance | 25 | N+1 queries, timeouts |
| Security | 25 | Auth, injection, access control |
| Concurrency | 15 | Race conditions, thread safety |
| Saga | 5 | Distributed transactions |

## Success Criteria

- All 300+ tests pass
- No N+1 queries
- No race conditions under concurrent load
- All events processed exactly once
- No security vulnerabilities
- All sagas complete or compensate properly
- Financial calculations are precise

## Hints

1. Start with L category bugs - services may not start correctly
2. Use `docker compose logs <service>` to see errors
3. The shared library contains cross-cutting bugs affecting all services
4. Check Kafka consumer offset commits carefully
5. Watch for symbol vs string key issues in event payloads
6. Financial calculations need BigDecimal, not Float
7. Circuit breaker state must be stored in Redis, not memory
8. Distributed locks need TTL and proper cleanup

## Ruby Microservices Patterns to Watch

```ruby
# Mutable default argument (BUG)
def process(items = [])
 items << new_item # Modifies shared default
end

# Event payload symbol/string confusion (BUG)
event = { 'type' => 'order.created', 'data' => {} }
event[:type] # Returns nil!

# Non-atomic inventory update (BUG)
def reserve(quantity)
 return false if stock < quantity
 # Race condition window here
 update!(stock: stock - quantity)
end

# Should be:
def reserve(quantity)
 with_lock do
 return false if stock < quantity
 decrement!(:stock, quantity)
 end
end

# Float precision in money (BUG)
total = 19.99 + 5.99 + 3.99 # 29.969999999999995

# Should use BigDecimal:
total = BigDecimal('19.99') + BigDecimal('5.99') + BigDecimal('3.99')
```

## Running Individual Service Tests

```bash
# Gateway
docker compose exec gateway bundle exec rspec

# Auth
docker compose exec auth bundle exec rspec

# Catalog
docker compose exec catalog bundle exec rspec

# Inventory
docker compose exec inventory bundle exec rspec

# Orders
docker compose exec orders bundle exec rspec

# Payments
docker compose exec payments bundle exec rspec

# Shipping
docker compose exec shipping bundle exec rspec

# Search
docker compose exec search bundle exec rspec

# Notifications
docker compose exec notifications bundle exec rspec

# Analytics
docker compose exec analytics bundle exec rspec
```

## Debugging Scenarios

For realistic debugging practice, see the [scenarios/](./scenarios/) directory. These simulate production incidents, customer escalations, security audits, and operational alerts:

| Scenario | Type | Focus |
| [Flash Sale Inventory Oversell](./scenarios/01-flash-sale-inventory-oversell.md) | PagerDuty Incident | Race conditions in inventory reservation |
| [Payment Double Charges](./scenarios/02-payment-double-charge.md) | Customer Escalation | Financial precision and retry logic |
| [Kafka Event Chaos](./scenarios/03-kafka-event-chaos.md) | DataDog Alert | Event processing, ordering, idempotency |
| [Security Penetration Test](./scenarios/04-security-penetration-test.md) | Security Report | SQL injection, IDOR, auth weaknesses |
| [Black Friday Meltdown](./scenarios/05-black-friday-meltdown.md) | Post-Incident Review | Database, caching, circuit breaker failures |

Each scenario describes **symptoms only** - use them to practice realistic debugging without hints about specific code fixes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-warehouse fulfillment, pricing refactor, catalog optimization, subscriptions, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Recommendation Engine, Gift Cards, Returns Processing |

These tasks test different software engineering skills while using the same codebase.
