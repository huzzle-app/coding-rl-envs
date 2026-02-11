# ShopStream Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, customer escalations, security audits, and operational alerts you might encounter as an engineer on the ShopStream e-commerce platform team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, metrics, and user reports. Your task is to:

1. Analyze the symptoms and logs provided
2. Identify potential root causes
3. Investigate the relevant code paths
4. Locate and fix the buggy code
5. Verify the fix with tests and doesn't cause regressions

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-flash-sale-inventory-oversell.md](./01-flash-sale-inventory-oversell.md) | PagerDuty Incident | Critical | Inventory sold past zero, race conditions under load |
| [02-payment-double-charge.md](./02-payment-double-charge.md) | Customer Escalation | Urgent | Double charges, incorrect refunds, currency errors |
| [03-kafka-event-chaos.md](./03-kafka-event-chaos.md) | DataDog Alert | High | Event duplication, ordering issues, DLQ growth |
| [04-security-penetration-test.md](./04-security-penetration-test.md) | Security Report | Critical | SQL injection, IDOR, mass assignment, weak auth |
| [05-black-friday-meltdown.md](./05-black-friday-meltdown.md) | Post-Incident Review | SEV-1 | Database exhaustion, cache stampede, cascade failures |

## Difficulty Progression

These scenarios are ordered by investigation scope:

- **Scenario 1**: Focused on concurrency bugs in inventory and cart management
- **Scenario 2**: Financial precision and payment retry logic issues
- **Scenario 3**: Event-driven architecture problems across multiple services
- **Scenario 4**: Security vulnerabilities requiring code review across the platform
- **Scenario 5**: Cross-cutting infrastructure and performance issues (most complex)

## Tips for Investigation

1. **Run tests to reproduce**: `docker compose exec <service> bundle exec rspec`
2. **Check for race conditions**: Look for non-atomic operations on shared state
3. **Trace event flows**: Follow Kafka events from producer to consumer
4. **Review financial code**: Look for Float vs BigDecimal issues
5. **Check security patterns**: Validate parameterized queries, ownership checks, strong params
6. **Examine callbacks**: ActiveRecord callbacks can have unexpected side effects

## Common Ruby/Rails Patterns to Watch

```ruby
# Race condition - check-then-act without locking
def reserve(quantity)
  return false if stock < quantity
  # Race window - another request can pass check
  update!(stock: stock - quantity)
end

# Float precision in money
total = 19.99 + 5.99  # => 25.979999999999997

# Symbol vs String keys in events
event = { 'type' => 'order.created' }
event[:type]  # => nil (should use event['type'])

# Mutable default argument
def process(items = [])
  items << new_item  # Modifies shared default!
end

# Missing eager loading (N+1)
orders.each { |o| puts o.line_items.map(&:product) }
```

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation with 75 bugs across 10 services
- Test files in each service's `spec/` directory contain assertions that exercise these bugs

## Service Architecture Reference

| Service | Port | Focus Areas |
|---------|------|-------------|
| Gateway | 8000 | Rate limiting, circuit breakers, routing |
| Auth | 8001 | JWT, sessions, API keys |
| Catalog | 8002 | Product cache, categories |
| Inventory | 8003 | Stock reservations, locking |
| Orders | 8004 | Pricing, cart, order state |
| Payments | 8005 | Transactions, refunds, currency |
| Shipping | 8006 | Shipment state machine |
| Search | 8007 | Elasticsearch, query parsing |
| Notifications | 8008 | Email jobs, templates |
| Analytics | 8009 | Reporting, projections |
