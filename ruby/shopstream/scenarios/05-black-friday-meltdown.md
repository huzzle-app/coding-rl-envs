# Post-Incident Report: Black Friday Service Degradation

## Incident Summary

**Incident ID**: INC-2024-BF-001
**Duration**: 4 hours 23 minutes
**Severity**: SEV-1 (Critical)
**Date**: November 29, 2024 (Black Friday)
**Services Affected**: All

---

## Executive Summary

During peak Black Friday traffic, ShopStream experienced cascading failures across multiple services. The incident resulted in approximately $2.1M in lost revenue, 47,000 abandoned carts, and significant customer dissatisfaction. Root causes included database connection exhaustion, cache stampedes, and circuit breaker misconfigurations.

---

## Timeline

**06:00 EST** - Traffic begins ramping up (5x normal)

**07:15 EST** - First alerts: Orders service response time > 2s
```
WARNING: orders-service latency p99 = 2,340ms (threshold: 500ms)
```

**07:22 EST** - Database connection pool exhausted on Orders service
```
CRITICAL: PG::ConnectionBad - could not connect to server
Active connections: 100/100 (max)
Waiting queries: 847
```

**07:25 EST** - Circuit breakers start opening
```
WARNING: Circuit breaker OPEN for inventory-service
WARNING: Circuit breaker OPEN for payments-service
```

**07:30 EST** - Cache stampede begins on Catalog service
```
WARNING: Redis CPU 100%
WARNING: Cache miss rate 94% (normal: 5%)
ERROR: Product cache returning nil for 12,000+ SKUs
```

**07:35 EST** - Cascade failure begins
```
CRITICAL: Gateway timeout rate 67%
CRITICAL: Cart service unavailable
CRITICAL: Checkout flow broken
```

**07:45 EST** - Customer-facing impact confirmed
- "Add to Cart" failing for 80% of users
- Checkout page returning 502 errors
- Product pages loading with missing data

**08:00 EST** - War room assembled

**09:30 EST** - Partial recovery after emergency scaling

**11:23 EST** - Full service restoration

---

## Technical Analysis

### Issue 1: Database Connection Pool Exhaustion

The Orders service database configuration had a connection pool of 100 connections, insufficient for Black Friday load.

```yaml
# database.yml
production:
  pool: 100  # Static value, not scaled with replicas
  checkout_timeout: 5  # Too long, causes request queuing
```

Additionally, raw SQL queries in the metrics service were leaking connections:

```
2024-11-29T07:22:15.123Z [ERROR] Connection checkout timeout
2024-11-29T07:22:15.234Z [WARN] metrics_service: connection not returned to pool
2024-11-29T07:22:15.345Z [WARN] bulk_processor: prepared statement not closed
```

### Issue 2: Cache Stampede

When the product cache TTL expired at 07:30, thousands of concurrent requests tried to regenerate the same cached data simultaneously:

```
2024-11-29T07:30:00.001Z [CACHE] product_cache TTL expired
2024-11-29T07:30:00.002Z [CACHE] 4,892 concurrent requests for product_123
2024-11-29T07:30:00.003Z [CACHE] All requests hitting database
2024-11-29T07:30:01.234Z [CACHE] Database query time: 2.3s per request
# Every request regenerates cache instead of one
```

The cache service had no stampede protection:

```
2024-11-29T07:30:05.567Z [WARN] product_cache: no lock acquired, all requests proceeding
```

### Issue 3: Circuit Breaker Misconfiguration

Circuit breakers were configured with shared state in memory instead of distributed storage:

```
2024-11-29T07:25:00.123Z [CB] Instance pod-1: circuit OPEN for inventory-service
2024-11-29T07:25:00.234Z [CB] Instance pod-2: circuit CLOSED for inventory-service
2024-11-29T07:25:00.345Z [CB] Instance pod-3: circuit OPEN for inventory-service
# Inconsistent state across instances
```

Additionally, the health check endpoint was masking underlying failures:

```
GET /health HTTP/1.1

# Returns 200 OK even when:
# - Database unreachable
# - Redis disconnected
# - Kafka consumer stopped
```

### Issue 4: Service Registry Stale Data

The Gateway service was routing to terminated instances:

```
2024-11-29T07:35:00.123Z [GATEWAY] Routing to inventory-pod-7 (terminated 5min ago)
2024-11-29T07:35:00.234Z [GATEWAY] Connection refused
2024-11-29T07:35:00.345Z [GATEWAY] Registry still shows inventory-pod-7 as healthy
```

### Issue 5: N+1 Query Under Load

Order serialization triggered N+1 queries, amplified under load:

```
# Single order API response generating 47 queries:
Order.find(123)                      # 1 query
order.line_items.each { |li|         # 1 query
  li.product                         # +N queries
  li.product.category                # +N queries
  li.product.images                  # +N queries
}
```

### Issue 6: Request Timeout Too Short

Gateway timeout was shorter than downstream service chains:

```
Gateway timeout: 5s
  → Orders service: 3s
    → Inventory check: 2s
    → Payment auth: 2s
# Total chain: 7s > Gateway timeout of 5s
```

### Issue 7: Missing Correlation IDs

Debugging was hampered by inability to trace requests across services:

```
[GATEWAY]      Request received (no trace ID)
[ORDERS]       Processing order (no trace ID)
[INVENTORY]    Stock check (no trace ID)
[PAYMENTS]     Auth request (no trace ID)
# Cannot correlate which gateway request caused which downstream calls
```

---

## Impact Metrics

| Metric | Normal | During Incident | Impact |
|--------|--------|-----------------|--------|
| Checkout success rate | 94% | 12% | -82% |
| Cart abandonment | 23% | 78% | +55% |
| Average response time | 180ms | 8,400ms | 47x slower |
| Revenue/hour | $180K | $32K | -$148K/hr |
| Customer complaints | 50/hr | 2,400/hr | 48x increase |

**Total Estimated Loss**: $2.1M revenue + $300K in customer credits

---

## Slack War Room Highlights

**@sre.lead** (07:45):
> Everything is on fire. Database connections maxed, cache miss rate through the roof, circuit breakers flapping.

**@dev.orders** (07:52):
> Orders DB pool is at 100/100. We're leaking connections somewhere. Metrics service raw SQL isn't returning connections to pool.

**@dev.catalog** (08:00):
> Cache stampede. Our product cache expired and 5000 requests all tried to rebuild it at once. No locking mechanism.

**@dev.gateway** (08:15):
> Health checks are lying. Services report healthy but they're actually degraded. We're routing to dead pods.

**@sre.lead** (08:30):
> Circuit breakers aren't coordinating. Each pod has different breaker state. Need to move state to Redis.

**@dev.orders** (09:00):
> Found N+1 in order serializer. Under load it's generating 50+ queries per order. Need to eager load associations.

---

## Files to Investigate

Based on symptoms:
- `orders/config/database.yml` - Connection pool sizing
- `analytics/services/metrics_service.rb` - Connection leak
- `orders/services/bulk_processor.rb` - Prepared statement leak
- `catalog/services/product_cache.rb` - Cache stampede protection
- `gateway/lib/circuit_breaker.rb` - Distributed state
- `gateway/lib/service_registry.rb` - Stale endpoints
- `gateway/controllers/health_controller.rb` - Health check accuracy
- `orders/serializers/order_serializer.rb` - N+1 queries
- `gateway/middleware/timeout.rb` - Timeout configuration
- `shared/lib/request_context.rb` - Correlation ID propagation
- `orders/services/fulfillment_service.rb` - Cascade failure handling

---

## Action Items

| Priority | Action | Owner | Status |
|----------|--------|-------|--------|
| P0 | Fix connection pool exhaustion | @db-team | Open |
| P0 | Implement cache stampede protection | @cache-team | Open |
| P0 | Fix circuit breaker state sharing | @platform-team | Open |
| P0 | Fix health check accuracy | @sre-team | Open |
| P1 | Fix N+1 queries in serializers | @orders-team | Open |
| P1 | Implement correlation ID propagation | @platform-team | Open |
| P1 | Review and fix timeout chains | @gateway-team | Open |
| P2 | Load test before next sale event | @qa-team | Open |

---

**Incident Commander**: Sarah Chen
**Post-Mortem Date**: December 2, 2024
**Next Review**: December 9, 2024
