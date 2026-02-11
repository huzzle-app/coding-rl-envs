# Customer Escalation: Alert Storm and Notification Chaos

## Zendesk Ticket #91847

**Priority**: Urgent
**Customer**: TechStream Analytics (Enterprise Tier)
**Account Value**: $380,000 ARR
**CSM**: Rachel Kim
**Created**: 2024-01-16 08:45 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We've been experiencing a nightmare with our DataNexus alerting over the past 48 hours. Our on-call team received over 2,000 alert notifications for issues that weren't real, while simultaneously missing actual outages. Our CEO got paged at 3 AM for a non-issue. This is causing serious alert fatigue and eroding trust in the platform.

### Reported Symptoms

1. **Alert Flood**: Single metric threshold violations generating 10-20 duplicate notifications within minutes

2. **Flapping Alerts**: Alerts firing, resolving, and re-firing repeatedly without actual metric changes

3. **Missed Escalations**: Critical alerts that should have escalated to PagerDuty never did

4. **Timezone Confusion**: Maintenance windows configured in EST not silencing alerts correctly

5. **Threshold Precision Issues**: Alerts for "CPU > 80%" firing when CPU is exactly 80.0%

---

## Technical Details from Customer Logs

### Alert Notification Log
```
2024-01-15T21:00:01Z [ALERT] cpu_usage > 80.0 triggered (value: 80.00000001)
2024-01-15T21:00:15Z [ALERT] cpu_usage > 80.0 triggered (value: 80.00000002)
2024-01-15T21:00:31Z [ALERT] cpu_usage > 80.0 triggered (value: 80.00000001)
2024-01-15T21:00:45Z [ALERT] cpu_usage > 80.0 triggered (value: 80.00000003)
2024-01-15T21:01:02Z [ALERT] cpu_usage > 80.0 triggered (value: 80.00000001)
# Note: 5 notifications in 1 minute for essentially the same value
```

### Escalation Timer Behavior
```
2024-01-15T22:15:00Z [ALERT] disk_full fired, escalation timer started (300s)
2024-01-15T22:15:05Z [ALERT] disk_full value fluctuated, new alert created
2024-01-15T22:15:05Z [ALERT] disk_full escalation timer started (300s)
# Original timer still running...
2024-01-15T22:20:00Z [ESCALATE] disk_full escalated to critical
2024-01-15T22:20:05Z [ESCALATE] disk_full escalated to critical (duplicate!)
```

### Recovery Detection Issues
```
2024-01-15T23:30:00Z [ALERT] memory_usage > 90% fired (value: 91.2)
2024-01-15T23:30:15Z [RESOLVE] memory_usage resolved (value: 89.9)
2024-01-15T23:30:30Z [ALERT] memory_usage > 90% fired (value: 90.1)
2024-01-15T23:30:45Z [RESOLVE] memory_usage resolved (value: 89.8)
2024-01-15T23:31:00Z [ALERT] memory_usage > 90% fired (value: 90.05)
# Value hovering near threshold causes rapid flapping
```

### Silence Window Timezone Failure
```
Customer configured:
  silence_start: "2024-01-16T02:00:00"  (intended: 2 AM EST = 7 AM UTC)
  silence_end: "2024-01-16T06:00:00"    (intended: 6 AM EST = 11 AM UTC)

Actual behavior:
  Alerts silenced from 2 AM UTC to 6 AM UTC
  Maintenance window from 2-6 AM EST (7-11 AM UTC) NOT silenced
  Customers received alerts during their planned maintenance
```

---

## Internal Slack Thread

**#eng-alerts** - January 16, 2024

**@rachel.kim** (09:15):
> TechStream Analytics is threatening to churn. Their on-call team is getting destroyed by alert spam. Can someone investigate urgently?

**@dev.jordan** (09:28):
> Looking at their alert configuration. The threshold for cpu_usage is set to 80.0 exactly. I'm seeing notifications for values like 80.00000001.

**@dev.sarah** (09:35):
> That's a float precision problem. We're using direct `>` comparison:
> ```javascript
> triggered = value > rule.threshold;
> ```
> With float math, 0.1 + 0.2 = 0.30000000000000004, not 0.3

**@dev.jordan** (09:42):
> The deduplication window is set to 5 minutes but I'm seeing duplicates within seconds. Let me check the dedup logic...

**@dev.sarah** (09:48):
> Found it. The dedup uses the last notification timestamp, but if the value fluctuates slightly, it creates a new alert ID. Each "new" alert bypasses deduplication.

**@dev.jordan** (09:55):
> The escalation timer issue is worse. Every time a metric fluctuates, we start a NEW timer without canceling the old one. That's why they're getting multiple escalation notifications.

**@sre.marcus** (10:05):
> Also seeing the silence window problem. Their timestamps don't include timezone suffix, so we're parsing them as local server time instead of the customer's timezone.

**@dev.sarah** (10:12):
> The flapping is because recovery detection has no hysteresis. A single reading below threshold marks the alert as resolved. One reading above fires it again. Need to require consecutive readings.

**@dev.jordan** (10:20):
> And the anomaly detection baseline never updates after initialization. First data point becomes the permanent baseline. Any deviation looks like an anomaly forever.

---

## Reproduction Steps

1. Create an alert rule with threshold `> 80.0`
2. Send metrics with values: 80.00000001, 79.99999999, 80.00000002
3. Observe:
   - Multiple notifications for essentially the same value
   - Rapid resolve/fire cycle
   - Multiple escalation timers running simultaneously

4. Configure a silence window with non-UTC timestamp
5. Observe alerts still firing during intended silence period

## Impact Assessment

- **Users Affected**: ~50 alert rules, ~200 engineers receiving notifications
- **Alert Fatigue Risk**: Critical - team ignoring alerts due to false positives
- **Missed Incidents**: 3 actual production issues were missed in the noise
- **SLA Status**: At risk of breach

---

## Files to Investigate

Based on the error patterns:
- `services/alerts/src/services/detection.js` - Alert threshold and deduplication logic
- Alert escalation timer management
- Silence window timezone handling
- Recovery detection and hysteresis

---

**Assigned**: @dev.jordan, @dev.sarah
**Deadline**: EOD January 17, 2024
**Follow-up Call**: Scheduled with customer for January 18, 2024 09:00 PST
