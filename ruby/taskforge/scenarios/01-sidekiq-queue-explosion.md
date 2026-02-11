# Incident Report: Sidekiq Queue Explosion

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-18 09:15 UTC
**Acknowledged**: 2024-01-18 09:18 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: Sidekiq queue depth exceeds threshold
Metric: sidekiq.queue.depth
Queue: notifications
Threshold: >50000 jobs
Current Value: 847,293 jobs (growing)
Rate: +15,000 jobs/minute
```

## Timeline

**09:15 UTC** - Alert triggered: Notifications queue depth exceeded 50,000

**09:22 UTC** - Secondary alert: Redis memory at 89%

**09:35 UTC** - Queue depth reached 250,000, Redis at 94%

**09:42 UTC** - Manual intervention: Paused Sidekiq workers to prevent Redis OOM

**09:50 UTC** - Queue depth stabilized at 847,293 pending jobs

## Grafana Dashboard Observations

### Queue Metrics
```
Queue: notifications
Jobs enqueued (last hour):
  09:00 - 09:15:  12,847 jobs
  09:15 - 09:30:  89,234 jobs
  09:30 - 09:45:  145,891 jobs
  09:45 - 10:00:  599,321 jobs (workers paused at 09:42)

Jobs processed (last hour):
  09:00 - 09:15:  12,102 jobs
  09:15 - 09:30:  14,234 jobs (falling behind)
  09:30 - 09:45:  15,001 jobs (severely behind)
```

### Job Pattern Analysis
```
Job class distribution (sampled from queue):
  NotificationJob:     42%
  ProjectStatsJob:     38%
  PushNotificationJob: 20%

ProjectStatsJob arguments (sample):
  All jobs reference same project_id: 4821

NotificationJob failures:
  RecordNotFound errors: 12,847
  No retry exhaustion logged (jobs retrying forever?)
```

### Redis Memory
```
09:00  2.1 GB (baseline)
09:15  2.8 GB
09:30  4.2 GB
09:45  6.1 GB (89% of 7GB limit)
10:00  6.4 GB (94% - critical)
```

## What Triggered This

Product team pushed a batch task update to Project #4821 ("Q1 Marketing Campaign") at 09:14 UTC:
- 847 tasks updated simultaneously via CSV import
- Each task update appears to trigger multiple background jobs
- Jobs appear to be spawning additional jobs recursively

## Slack Thread

**#eng-incidents** - January 18, 2024

**@sre.alex** (09:20):
> Sidekiq queue exploding. Something is spawning jobs faster than we can process them. Looks like it started after a bulk task update on project 4821.

**@dev.maria** (09:25):
> Looking at the job arguments. Every ProjectStatsJob has the same project_id. Why are we queueing the same job hundreds of thousands of times?

**@dev.chen** (09:28):
> Found something. Each task save triggers a ProjectStatsJob. When you update 847 tasks, that's 847 stats jobs. But that doesn't explain the exponential growth...

**@dev.maria** (09:32):
> Wait - the stats job might be updating something that triggers more jobs. I'm seeing the job count still growing even after the CSV import finished.

**@sre.alex** (09:35):
> Also seeing a lot of NotificationJob failures with RecordNotFound. But the jobs aren't going to the dead queue. They just keep retrying?

**@dev.chen** (09:40):
> Checked NotificationJob - there's no retry limit configured. And the rescue block just returns nil without any logging. These jobs are silently failing and retrying forever.

**@sre.alex** (09:42):
> Pausing workers before Redis runs out of memory. We need to figure out:
> 1. Why are stats jobs spawning infinitely?
> 2. Why aren't failed notification jobs dying?
> 3. How do we safely clear the queue without losing legitimate jobs?

## Server Logs (Sample)

```
2024-01-18T09:15:12Z [Sidekiq] INFO: ProjectStatsJob started project_id=4821
2024-01-18T09:15:12Z [Sidekiq] INFO: ProjectStatsJob started project_id=4821
2024-01-18T09:15:12Z [Sidekiq] INFO: ProjectStatsJob started project_id=4821
2024-01-18T09:15:13Z [Sidekiq] INFO: ProjectStatsJob started project_id=4821
# Pattern continues - hundreds of identical jobs

2024-01-18T09:15:45Z [Sidekiq] WARN: NotificationJob failed: ActiveRecord::RecordNotFound
# Note: No "job moving to dead queue" log entry follows

2024-01-18T09:16:02Z [Sidekiq] INFO: NotificationJob started user_id=12345 event=task_assigned
2024-01-18T09:16:02Z [Sidekiq] WARN: NotificationJob failed: ActiveRecord::RecordNotFound
# Same job retrying immediately
```

## Customer Impact

- Email notifications delayed (queue backed up)
- Push notifications not being delivered
- Project dashboards showing stale data
- API response times increased (Redis under memory pressure)

## Questions for Investigation

1. What callback or job is causing the infinite ProjectStatsJob spawning loop?
2. Why aren't NotificationJob failures being logged properly?
3. Why do failed jobs keep retrying instead of going to the dead queue?
4. Is there similar job spawning behavior in other parts of the codebase?

## Files to Investigate

Based on the job classes involved:
- `app/jobs/notification_job.rb`
- `app/jobs/project_stats_job.rb`
- `app/models/task.rb` (triggers stats job on save)
- `app/models/organization.rb` (check callbacks)

---

**Status**: INVESTIGATING
**Assigned**: @dev.maria, @dev.chen
**Follow-up**: Post-incident review scheduled for 2024-01-19 14:00 UTC
