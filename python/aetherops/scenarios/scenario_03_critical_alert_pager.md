# Scenario 03: Critical Alerts Not Reaching On-Call Pagers

## Jira Ticket: AOPS-4892

**Type:** Bug
**Priority:** Critical
**Component:** Notifications Service
**Reporter:** Marcus Thompson (On-Call Manager)
**Assignee:** Unassigned

---

### Description

On-call engineers are not receiving pager notifications for severity-5 (critical) incidents. The notification service is sending email, SMS, dashboard, and Slack alerts, but **pager alerts are missing entirely for the highest severity level**.

This was discovered during the post-mortem for the STARSAT-12 attitude control anomaly, where the on-call engineer was asleep and only saw the Slack notification 45 minutes later.

### Steps to Reproduce

1. Trigger a severity-5 incident (e.g., critical thermal warning)
2. Observe the notification channels selected by the system
3. Note that "pager" is absent from the channel list

### Expected Behavior

For severity >= 5, notifications should be sent to ALL channels including:
- email
- sms
- **pager** (MISSING)
- dashboard
- slack

### Actual Behavior

Severity-5 incidents notify via: `["email", "sms", "dashboard", "slack"]`
Pager channel is not included.

### Test Failures

```
tests/services/notifications_test.py::NotificationsServiceTest::test_critical_channels
tests/integration/service_mesh_flow_test.py::test_notification_routing_severity_5
tests/stress/service_mesh_matrix_test.py::test_notification_channel_coverage_*
```

### Root Cause Investigation

The `NotificationPlanner.plan_channels()` method in `services/notifications/service.py` appears to have an incomplete channel list for the severity >= 5 case.

### Business Impact

- 45-minute delay in response to STARSAT-12 anomaly
- On-call escalation SLA breached (15-minute response required for sev-5)
- Regulatory audit finding expected (NASA-COM-7 compliance)

### Related Documentation

- Notification routing policy: docs/notification-policy.md
- On-call escalation matrix: docs/oncall-matrix.md
- Severity definitions: aetherops/models.py

---

### Comments

**@sarah.chen** - 2026-01-20 09:15 UTC

This is really bad. Pager is supposed to be the highest priority channel. We use it specifically because engineers silence everything else at night.

**@marcus.thompson** - 2026-01-20 09:18 UTC

Agreed. The channel list in the code needs to include "pager" for critical alerts. Not sure how this was missed during initial implementation.
