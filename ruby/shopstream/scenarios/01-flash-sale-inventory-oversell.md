# Incident Report: Flash Sale Inventory Oversold

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-10 11:02 UTC
**Acknowledged**: 2024-02-10 11:05 UTC
**Team**: E-Commerce Platform

---

## Alert Details

```
CRITICAL: Inventory oversold for SKU-FLASH-2024-001
Event: INVENTORY_NEGATIVE_STOCK
SKU: FLASH-WINTER-JACKET-BLK-M
Quantity Available: -47
Orders Affected: 147 (100 units available at sale start)
```

## Timeline

**11:00 UTC** - Flash sale begins for limited-edition winter jacket (100 units)

**11:00:15 UTC** - First 50 orders placed successfully

**11:00:45 UTC** - Inventory service starts logging warnings about concurrent reservation attempts

**11:01:30 UTC** - Stock count shows -23 (oversold by 23 units)

**11:02:00 UTC** - Alert triggered for negative inventory

**11:05:00 UTC** - Flash sale paused manually by operations team

**11:10:00 UTC** - Final oversell count: 47 extra orders for unavailable inventory

## Grafana Dashboard Observations

### Concurrent Requests
```
Metric: inventory_reservation_requests_concurrent
Time: 11:00 - 11:05 UTC

Peak concurrent reservations: 87 per second
Average response time: 234ms
Reservation success rate: 147% (should never exceed 100%)
```

### Database Lock Contention
```
Metric: pg_stat_activity_waiting
Time: 11:00 - 11:05 UTC

Waiting queries: 45+
Lock timeouts: 12
Deadlock detections: 3
```

### Order Events
```
order.created events: 147
inventory.reserved events: 147
inventory quantity decremented: 147 times
But starting quantity was only 100
```

## Customer Impact

- 47 customers will need order cancellations and refunds
- Social media complaints about "bait and switch"
- Customer support queue: 200+ tickets in 30 minutes
- Estimated revenue loss from goodwill credits: $4,700

## Application Logs

```
2024-02-10T11:00:15.123Z [INVENTORY] Checking stock for SKU-FLASH-2024-001: 100 available
2024-02-10T11:00:15.125Z [INVENTORY] Reserving 1 unit for order ORD-001
2024-02-10T11:00:15.127Z [INVENTORY] Checking stock for SKU-FLASH-2024-001: 100 available
2024-02-10T11:00:15.128Z [INVENTORY] Reserving 1 unit for order ORD-002
# Note: Both requests saw 100 available before either completed
2024-02-10T11:00:15.234Z [INVENTORY] Stock updated: 99
2024-02-10T11:00:15.235Z [INVENTORY] Stock updated: 99
# Both decremented from 100, not sequential
```

### Deeper Investigation

```
2024-02-10T11:00:45.892Z [WARN] Reservation service: stock check passed but update may have raced
2024-02-10T11:01:30.445Z [ERROR] Stock count negative for warehouse WH-EAST: -23
2024-02-10T11:01:45.001Z [ERROR] StockMovement callback triggered but parent update incomplete
```

## Previous Occurrences

This is the third flash sale with overselling issues this quarter:
- Jan 15: 12 oversold units (lower traffic event)
- Jan 28: 8 oversold units (regional sale)
- Feb 10: 47 oversold units (site-wide sale)

Pattern suggests the bug scales with concurrent traffic.

## Attempted Mitigations During Incident

1. Increased database connection pool - no improvement
2. Added Redis-based rate limiting on checkout - slightly helped
3. Manual sale pause - only solution that worked

## Questions for Investigation

1. Why does the inventory check pass for multiple concurrent requests?
2. Is there proper locking when decrementing stock?
3. Are we using database-level atomic operations or application-level checks?
4. Why does the stock movement callback log suggest incomplete parent updates?
5. Is optimistic locking configured on the inventory/order models?

## Related Services

Based on logs, investigation should focus on:
- `inventory` service - reservation logic
- `orders` service - cart modification and order placement
- Shared library - event processing for concurrent events

---

**Status**: INVESTIGATING
**Assigned**: @backend-team
**Business Impact**: HIGH - Customer trust, refund costs, social media exposure
**RCA Due**: 2024-02-12 EOD
