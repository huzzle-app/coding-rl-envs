# Incident Report: Event Processing Failures and Data Inconsistency

## DataDog Alert

**Severity**: High (P2)
**Triggered**: 2024-02-09 08:15 UTC
**Team**: Platform Engineering

---

## Alert Details

```
WARNING: Kafka consumer lag exceeding threshold
Topic: shopstream.orders.events
Consumer Group: inventory-service
Current Lag: 45,892 messages
Threshold: 1,000 messages

WARNING: Dead Letter Queue growing
Topic: shopstream.dlq
Messages: 2,341 (24h)
Normal baseline: <50
```

## Symptoms Observed

### 1. Order Status Inconsistency

Orders are stuck in incorrect states across services:

```
Order ORD-112233:
  - Orders Service: status = "paid"
  - Inventory Service: status = "pending_reservation"
  - Shipping Service: status = "unknown"
  - Analytics: no record exists
```

### 2. Duplicate Event Processing

Same events being processed multiple times:

```
2024-02-09T08:00:12.345Z [ORDERS] Processing payment.processed event for ORD-112233
2024-02-09T08:00:12.567Z [ORDERS] Order ORD-112233 marked as paid
2024-02-09T08:00:15.123Z [ORDERS] Processing payment.processed event for ORD-112233
2024-02-09T08:00:15.234Z [ORDERS] Order ORD-112233 marked as paid (duplicate)
2024-02-09T08:00:18.456Z [ORDERS] Processing payment.processed event for ORD-112233
2024-02-09T08:00:18.567Z [ORDERS] Order ORD-112233 marked as paid (triplicate)
```

### 3. Events Processed Out of Order

```
2024-02-09T08:05:00.001Z [INVENTORY] Received: order.shipped for ORD-445566
2024-02-09T08:05:00.002Z [INVENTORY] ERROR: Cannot ship - order not yet paid
2024-02-09T08:05:05.001Z [INVENTORY] Received: order.paid for ORD-445566
# Events arrived out of order - shipped before paid
```

### 4. Lost Events During Replay

After a service restart, event replay corrupted state:

```
2024-02-09T07:30:00.000Z [INVENTORY] Service starting, replaying events...
2024-02-09T07:30:05.234Z [INVENTORY] Replayed 10,000 events
2024-02-09T07:30:05.235Z [INVENTORY] WARNING: Stock count mismatch
2024-02-09T07:30:05.236Z [INVENTORY] Expected: 500, Actual: 487
2024-02-09T07:30:05.237Z [INVENTORY] WARNING: 13 units unaccounted for
```

---

## Grafana Metrics

### Consumer Lag Over Time
```
Time        | inventory-consumer | orders-consumer | analytics-consumer
08:00       | 234               | 12              | 8,923
08:15       | 12,456            | 45              | 15,234
08:30       | 45,892            | 89              | 28,456
08:45       | 67,234            | 123             | 41,234
```

### Event Processing Rates
```
Metric: kafka_consumer_records_consumed_rate
Expected: ~500/sec
Actual: 50-80/sec (inventory), 480/sec (orders)
```

### Dead Letter Queue
```
Events in DLQ by error type:
- "deserialization_failed": 892
- "handler_exception": 1,234
- "timeout_exceeded": 215
```

---

## Slack Thread: #platform-incidents

**@sre.oncall** (08:20):
> Kafka consumer lag is through the roof on inventory service. Anyone know what's going on?

**@dev.platform** (08:25):
> Looking at it. The inventory consumer seems to be committing offsets before fully processing messages. If processing fails after commit, we lose that event.

**@dev.platform** (08:35):
> Also found that events are being committed in batches, but individual failures within a batch aren't tracked. Partial batch processing with full batch commit.

**@dev.backend** (08:40):
> The duplicate processing might be related. I see we're not checking idempotency keys in the payment consumer. Same event gets processed every time it's retried.

**@sre.oncall** (08:50):
> Why is the DLQ not being processed? Those events are just piling up.

**@dev.platform** (08:55):
> Checked the DLQ processor - it reads messages but doesn't actually do anything with them. Looks like the implementation was never completed.

**@dev.backend** (09:05):
> Found another issue - the event serializer has a version mismatch. Events with schema v2 are being deserialized as v1, causing the deserialization failures in DLQ.

**@dev.analytics** (09:15):
> Our projection service is also way behind. Seems like there's a delay between event publish and when our projections see it. Customers are seeing stale order data.

---

## Customer-Facing Issues

1. **Order Status Page Stale**: Customers see "Processing" when order was shipped hours ago
2. **Duplicate Emails**: Some customers received 3-4 "Order Confirmed" emails for single order
3. **Inventory Mismatch**: Products showing "In Stock" on website but order fails with "Out of Stock"
4. **Missing Orders**: Some orders exist in payment system but not in order history

## Service Startup Issues

When the Kafka consumer was restarted this morning:

```
2024-02-09T07:28:45.123Z [KAFKA] Consumer starting...
2024-02-09T07:28:45.234Z [KAFKA] Connecting to broker kafka-1:9092
2024-02-09T07:28:55.234Z [KAFKA] Connection timeout after 10s
2024-02-09T07:28:55.235Z [KAFKA] Retrying connection...
2024-02-09T07:29:05.234Z [KAFKA] Connection timeout after 10s
2024-02-09T07:29:05.235Z [KAFKA] Giving up after 2 retries
2024-02-09T07:29:05.236Z [KAFKA] Service starting without Kafka connection
# Service started but consumer never connected - silent failure
```

---

## Questions for Investigation

1. Why are offsets being committed before processing completes?
2. Why is idempotency not being checked on event handlers?
3. Why does event replay corrupt state instead of reconstructing it correctly?
4. Why are events arriving out of order?
5. Why does the DLQ processor not actually process failed events?
6. Why does the Kafka consumer silently fail to connect on startup?
7. Why are concurrent event processors creating duplicates?

## Files to Investigate

Based on the symptoms:
- `shared/lib/kafka_consumer.rb` - Connection and offset commit issues
- `shared/lib/event_processor.rb` - Concurrent processing duplicates
- `shared/lib/event_store.rb` - Event ordering
- `shared/lib/event_serializer.rb` - Schema version compatibility
- `shared/lib/dlq_processor.rb` - DLQ not processing
- `orders/consumers/payment_consumer.rb` - Missing idempotency
- `inventory/services/event_replay_service.rb` - Replay corruption
- `analytics/services/projection_service.rb` - Projection lag

---

**Status**: INVESTIGATING
**Assigned**: @platform-team
**Impact**: Data consistency across all services compromised
**Recovery Plan**: Pending root cause analysis
