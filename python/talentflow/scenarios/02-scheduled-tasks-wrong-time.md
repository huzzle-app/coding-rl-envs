# Operations Incident: Scheduled Tasks Running at Wrong Times

## PagerDuty Alert

**Severity**: High (P2)
**Triggered**: 2024-01-19 13:00 UTC
**Acknowledged**: 2024-01-19 13:05 UTC
**Team**: Platform Engineering

---

## Alert Details

```
WARNING: Daily candidate scoring task completed during business hours
Expected: 3:00 AM Eastern
Actual: 8:00 AM Eastern
Impact: Performance degradation during peak usage
```

## Incident Summary

Multiple scheduled background tasks are firing at incorrect times. Tasks scheduled to run overnight are instead running during peak business hours, causing significant performance degradation and affecting user experience.

---

## Timeline

**Day 1 - 2024-01-15**:
- 08:00 EST: Heavy load alerts from API servers
- 08:05 EST: Investigation reveals `calculate_all_match_scores` task running
- 08:15 EST: Task normally scheduled for 03:00 EST

**Day 2 - 2024-01-16**:
- 08:00 EST: Same issue recurs
- HR managers complain about slow candidate searches during morning reviews

**Day 3 - 2024-01-17**:
- Pattern confirmed: All overnight tasks running 5 hours late
- Calculated offset matches UTC vs Eastern timezone difference (5 hours in January)

**Day 4 - 2024-01-19**:
- Issue escalated to platform engineering

---

## User Complaints

### Zendesk Ticket #89234
> **From**: sarah.hr@acmecorp.com
> **Subject**: System extremely slow every morning
>
> Every day around 8 AM, our TalentFlow instance becomes almost unusable. Candidate searches that normally take 1-2 seconds are timing out. This is impacting our morning hiring standups.

### Zendesk Ticket #89412
> **From**: john.recruiter@techstart.io
> **Subject**: Report generation failing at 8 AM
>
> I scheduled a daily hiring report to generate at 8 AM Eastern so I can review it first thing. But it keeps failing or timing out. Yesterday the report finally came through at 9:30 AM.

---

## Slack Discussion: #eng-platform

**@sre.kim** (09:15):
> We've been getting complaints about morning slowdowns for a week now. Finally traced it - Celery beat is firing tasks at the wrong times.

**@dev.sarah** (09:20):
> What's the offset? Maybe a timezone issue?

**@sre.kim** (09:23):
> Exactly 5 hours. So a task scheduled for 3 AM EST is running at 3 AM UTC, which is 8 AM EST (during winter, when offset is 5 hours).

**@dev.marcus** (09:28):
> Let me check the Celery config. Django is definitely configured for `America/New_York`...

**@dev.marcus** (09:35):
> Found it. In `celery.py`, there's a config override:
> ```python
> app.conf.timezone = 'UTC'
> app.conf.enable_utc = True
> ```
> This overrides whatever Django settings has.

**@dev.sarah** (09:38):
> So Django says one thing, Celery says another. That's why the tasks are off.

**@dev.marcus** (09:42):
> Also, Django settings has `CELERY_ENABLE_UTC = False` but the celery.py file sets `enable_utc = True`. Total mismatch.

**@sre.kim** (09:45):
> So all scheduled tasks in beat_schedule are being interpreted as UTC times, not Eastern. That explains the 5-hour shift.

---

## Grafana Observations

### CPU Usage Pattern (Last 7 Days)
```
Expected (overnight processing):
02:00-04:00 EST: 85% CPU (background tasks)
08:00-18:00 EST: 40% CPU (user traffic)

Actual:
02:00-04:00 EST: 15% CPU (nothing running)
08:00-10:00 EST: 95% CPU (background tasks + user traffic)
          ^ Severe contention
```

### Task Execution Times
```
Task: calculate_all_match_scores
Scheduled: 03:00 EST
Actual execution times (last 7 days):
  - 2024-01-13: 08:00 EST
  - 2024-01-14: 08:00 EST
  - 2024-01-15: 08:00 EST
  - 2024-01-16: 08:00 EST
  - 2024-01-17: 08:00 EST
  - 2024-01-18: 08:00 EST
  - 2024-01-19: 08:00 EST

Pattern: Consistent 5-hour offset (UTC vs EST winter offset)
```

---

## Configuration Analysis

### Django Settings (settings/base.py)
```python
TIME_ZONE = 'America/New_York'
USE_TZ = True
CELERY_ENABLE_UTC = False  # Expect Celery to use local time
```

### Celery Configuration (celery.py)
```python
# After loading from django settings:
app.conf.timezone = 'UTC'      # Override! Ignores Django TIME_ZONE
app.conf.enable_utc = True     # Override! Ignores CELERY_ENABLE_UTC

app.conf.beat_schedule = {
    'calculate-match-scores': {
        'task': 'apps.jobs.tasks.calculate_all_match_scores',
        'schedule': crontab(hour=3, minute=0),  # Interpreted as 3 AM UTC!
    },
    'send-daily-digest': {
        'task': 'apps.accounts.tasks.send_digest_emails',
        'schedule': crontab(hour=6, minute=0),  # Interpreted as 6 AM UTC!
    },
    # ... more tasks
}
```

---

## Impact

- **Performance**: 40% increase in response times during 8-10 AM EST
- **User Experience**: Timeouts and slow page loads during peak hours
- **Reliability**: Some scheduled tasks failing due to resource contention
- **Business**: HR teams unable to run morning hiring standups effectively

---

## Affected Tasks

| Task | Expected Time (EST) | Actual Time (EST) | Impact |
|------|---------------------|-------------------|--------|
| calculate_all_match_scores | 03:00 | 08:00 | CPU spike |
| cleanup_expired_tokens | 02:00 | 07:00 | Moderate |
| generate_analytics_reports | 04:00 | 09:00 | CPU spike |
| send_digest_emails | 06:00 | 11:00 | Email delays |
| sync_external_calendars | 05:00 | 10:00 | Moderate |

---

## Files to Investigate

- `talentflow/celery.py` - Celery app configuration
- `talentflow/settings/base.py` - Django timezone settings

---

## Proposed Solution Direction

Celery's timezone configuration needs to match Django's. The override in `celery.py` that sets timezone to UTC should be removed or aligned with Django's TIME_ZONE setting.

---

**Status**: INVESTIGATING
**Assigned**: @dev.marcus
**Priority**: High - affecting all enterprise customers
