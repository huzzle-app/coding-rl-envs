# ShopStream - E-Commerce Microservices Platform

## Architecture

The platform consists of 10 microservices:

| Service | Port | Purpose |
|---------|------|---------|
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

### Infrastructure Components

- **Kafka** - Event streaming between services
- **PostgreSQL 15** - Primary databases (per service)
- **Redis 7** - Caching, sessions, Sidekiq queues
- **Elasticsearch** - Product search indexing
- **Mailhog** - Email testing

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

# Run tests (will fail initially)
bundle exec rspec
```

## Known Issues

The test suite has multiple failures. Main issues appear to be in the core business logic and infrastructure layers.

## Key Challenges

### 1. Setup Hell

The services won't start correctly initially. You must fix these first:
- Kafka consumer connection failures
- Service discovery returning stale endpoints
- Database pool exhaustion under load
- Redis connection not thread-safe

### 2. Multi-Service Debugging

Bugs span multiple services. Many operations involve cross-service communication through Kafka events. Fixing one bug may reveal bugs in dependent services.

### 3. Bug Dependencies

Some bugs depend on others being fixed first (40-71% of bugs have prerequisites):
- L1 (Kafka connection) → E5 (Offset commit) → E1 (Event ordering) → E2 (Idempotency)
- A1 (Inventory race) → E7 (Saga compensation) → F8 (Cascade failure)
- H1 (Float precision) → H2 (Tax rounding) → H5 (Refund calculation)

### 4. Ruby-Specific Pitfalls

- Mutable default arguments silently sharing state
- Symbol vs String key confusion in event payloads
- Thread-unsafe memoization (@data ||= value)
- SQL injection via string interpolation
- Frozen string modification attempts

## Common Bug Patterns

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

# Float precision in money (BUG)
total = 19.99 + 5.99 + 3.99 # 29.969999999999995
# Should use BigDecimal

# SQL injection (BUG)
where("status = '#{params[:status]}'")
# Should be: where(status: params[:status])
```

## Test Categories

| Category | Tests | Focus |
|----------|-------|-------|
| Unit | 120 | Model validations, service methods |
| Integration | 80 | API endpoints, service interactions |
| Consumer | 30 | Kafka event handling |
| Performance | 25 | N+1 queries, timeouts |
| Security | 25 | Auth, injection, access control |
| Concurrency | 15 | Race conditions, thread safety |
| Saga | 5 | Distributed transactions |

## Success Criteria

- All tests pass
- Services start without errors
- No N+1 queries
- No race conditions under concurrent load
- All events processed exactly once
- No security vulnerabilities
- All sagas complete or compensate properly
- Financial calculations are precise

## Reward Function

The environment uses sparse rewards with 8 thresholds:

```
Pass Rate → Reward
< 10% → 0.00
10-25% → 0.05
25-40% → 0.12
40-55% → 0.22
55-70% → 0.38
70-85% → 0.55
85-95% → 0.78
100% → 1.00
```

Additional bonuses:
- **Security tests**: +0.08 for all security tests passing
- **Distributed systems**: +0.05 for event/saga tests passing
- **Financial tests**: +0.05 for precision/rounding tests passing
- **Regression penalty**: -0.15 for re-breaking tests

## Event-Driven Communication

Services communicate via Kafka events:
- `order.created` - New order placed
- `order.paid` - Payment confirmed
- `order.shipped` - Order shipped
- `inventory.reserved` - Stock reserved
- `inventory.released` - Stock released
- `payment.processed` - Payment completed
- `payment.refunded` - Refund issued

## Hints

1. Start with L category bugs - services may not start correctly
2. Use `docker compose logs <service>` to see errors
3. The shared library contains cross-cutting bugs affecting all services
4. Check Kafka consumer offset commits carefully
5. Watch for symbol vs string key issues in event payloads
6. Financial calculations need BigDecimal, not Float
7. Circuit breaker state must be stored in Redis, not memory
8. Distributed locks need TTL and proper cleanup
9. Use pessimistic locking (with_lock) for inventory operations
10. Event handlers must be idempotent (check idempotency keys)

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-warehouse fulfillment, pricing refactor, catalog optimization, subscriptions, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Recommendation Engine, Gift Cards, Returns Processing |

These tasks test different software engineering skills while using the same codebase.
