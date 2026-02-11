# Incident Report: Critical Alerts Not Reaching On-Call Engineers

**Incident ID:** INC-2024-0892
**Reported by:** Site Reliability Engineering
**Severity:** P1 - Critical
**Status:** Open
**Created:** 2024-03-18 03:45 UTC

## Summary

Severity-5 incidents are only triggering email notifications. Pager and SMS channels are not firing despite being configured for critical alerts.

## Symptoms

- On-call engineers only receive emails for critical incidents
- Pager duty shows no pages received in past 72 hours
- SMS gateway logs show no outbound messages
- Email notifications are working correctly
- Multiple critical incidents went unacknowledged for 30+ minutes

## Impact

- Missed 3 critical orbital anomaly alerts
- Delayed response to fuel pressure warning
- Potential safety implications for unattended critical events
- On-call SLA breached multiple times

## Expected Behavior

For severity >= 5 incidents:
1. Pager should fire immediately
2. SMS should be sent within 30 seconds
3. Email should be sent within 1 minute

All three channels should fire independently.

## Actual Behavior

Only the first channel (pager or email depending on timing) fires. Subsequent channels for the same incident+recipient are suppressed.

## Investigation Notes

1. Notification planner throttle is set to 10 minutes (correct)
2. First notification of each type sends successfully
3. Subsequent channels appear to be throttled as "duplicates"
4. Throttle key appears to be missing channel differentiation

## Relevant Logs

```
2024-03-18 03:42:15 INFO  notifications: planning alerts for incident=INC-FUEL-0023 severity=5
2024-03-18 03:42:15 DEBUG notifications: channels=['pager', 'sms', 'email']
2024-03-18 03:42:15 INFO  notifications: sending channel=pager recipient=ops-lead
2024-03-18 03:42:15 DEBUG notifications: throttle_key=('ops-lead', 'INC-FUEL-0023')
2024-03-18 03:42:15 WARN  notifications: throttled channel=sms key=('ops-lead', 'INC-FUEL-0023')
2024-03-18 03:42:15 WARN  notifications: throttled channel=email key=('ops-lead', 'INC-FUEL-0023')
```

## Failing Tests

- `test_severity_five_uses_all_channels`
- `test_multi_channel_not_collapsed`

## Immediate Mitigation

Temporarily disabled throttling (not recommended long-term due to alert fatigue risk).

## Questions for Engineering

1. How is the throttle key constructed?
2. Should channel be part of the deduplication key?
3. Was throttling logic recently modified?
