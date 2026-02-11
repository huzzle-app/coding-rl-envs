# Support Ticket SUP-2024-0847

## Ticket Details
**Priority**: High
**Category**: Grid Operations - Notifications
**Status**: Escalated to Engineering
**Customer**: Eastern Interconnection Control Center
**Reported By**: J. Martinez, Grid Operations Manager

---

## Customer Report

> We're experiencing intermittent issues with our grid alert notification system that are affecting our ability to respond to load imbalances.
>
> **Issue 1: Missing Notifications**
>
> Our operators report that some critical load shedding alerts are not being delivered. We have logging that shows the alerts were generated, but operators never received them. This has happened at least 4 times in the past week. When we query the notification cache for a user, sometimes we get their notification preferences back instead of their actual notifications, which makes no sense.
>
> **Issue 2: Slow Notification Delivery**
>
> During peak load periods (typically 6-8 AM and 5-7 PM), notification delivery slows to a crawl. We're seeing 30+ second delays on what should be instant alerts. Our monitoring shows the notification service CPU spiking during these windows even though message volume isn't that high.
>
> **Issue 3: Thundering Herd on Cache Miss**
>
> After a service restart, we see massive spikes in database queries. It looks like every request is hitting the database simultaneously instead of one request populating the cache. This compounds the slow delivery issue.
>
> **Issue 4: Notification Channel Updates Not Visible**
>
> When we update notification channels (e.g., switching from EMAIL to WEBHOOK for a specific alert type), the changes don't seem to propagate consistently. Some servers pick up the change immediately, others show the old channel. We've tried restarting services but the behavior is unpredictable.
>
> These issues are critical for grid reliability. Missing or delayed notifications during a load imbalance event could result in cascading failures.

---

## Support Investigation Notes

### Cache Behavior Analysis

Tested cache retrieval pattern:

```java
// First call: User notifications
notificationService.getUserNotifications(userId=42);
// Returns: ["Welcome notification", "System update"]  -- CORRECT

// Second call: User preferences (same user ID)
notificationService.getUserPreferences(userId=42);
// Returns: ["Welcome notification", "System update"]  -- WRONG! Should be preferences
```

Both methods appear to return the same cached data. The cache key pattern may not distinguish between notification types.

### Concurrency Under Load

Load test results show unusual blocking behavior:

```
Test: 100 concurrent notifications across 10 channels
Expected: ~5 seconds (50ms per notification, 10 parallel channels)
Actual: ~50 seconds (all channels appear to serialize)

Observation: Even notifications on DIFFERENT channels (EMAIL, SMS, PUSH)
block each other. Channels that should be independent are contending
for the same resource.
```

### Thread Dump During Slow Period

```
"notification-worker-1" BLOCKED on java.lang.String@0x7f8a2c3d4e5f
   at com.vertexgrid.notifications.service.NotificationService.sendNotification
   waiting for "notification-worker-3" to release lock

"notification-worker-3" BLOCKED on java.lang.String@0x7f8a2c3d4e5f
   at com.vertexgrid.notifications.service.NotificationService.sendNotification
   waiting for "notification-worker-1" to release lock

Note: Both threads are waiting on the SAME String object despite
processing different channels ("EMAIL" and "SMS")
```

### Channel Update Test

```
Server 1: notificationService.getNotificationChannels()[0] = "EMAIL"
         notificationService.updateChannel(0, "WEBHOOK")
         notificationService.getNotificationChannels()[0] = "WEBHOOK"  -- correct locally

Server 2: notificationService.getNotificationChannels()[0] = "EMAIL"  -- still old value!

Note: Both servers share the same database and were started from
identical deployments. The update is not consistently visible.
```

---

## Failing Tests

```
NotificationServiceTest.test_cache_key_collision
NotificationServiceTest.test_thundering_herd_single_load
NotificationServiceTest.test_concurrent_channel_send
NotificationServiceTest.test_volatile_array_visibility
NotificationServiceTest.test_template_overload_collision
```

---

## Metrics During Incident

```
notification_delivery_latency_seconds{quantile="p99"}: 34.7
notification_cache_hit_ratio: 0.23  (normally 0.95+)
notification_db_queries_per_second: 847 (normally 12)
notification_channel_contention_count: 2341
```

---

## Business Impact

- **Grid Safety**: 4 critical load alerts missed in past week
- **Response Time**: Average alert acknowledgment time increased from 12s to 47s
- **Operator Confidence**: Control room staff losing trust in notification system
- **Compliance Risk**: NERC CIP-007 requires reliable alert delivery

---

## Requested Investigation

1. Cache key generation logic for user notifications vs. preferences
2. Synchronization mechanism in `sendNotification()` method
3. Cache population strategy after cache miss
4. Visibility guarantees for notification channel array updates
5. Template caching for overloaded methods

---

## References

- Customer SLA Agreement: EICC-2023-001
- NERC CIP-007 Requirements: Section 4.3 - Security Event Alerting
- Previous Related Ticket: SUP-2024-0623 (cache performance)
