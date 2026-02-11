# Grafana Alert: Scheduler Jobs Stuck and Split-Brain

## Alert Details

**Triggered**: 2024-01-17 06:30 UTC
**Source**: DataNexus Scheduler Monitoring Dashboard
**Severity**: Critical

---

## Alert Summary

```
CRITICAL: scheduler.jobs.pending > 500 for 15 minutes
Host: datanexus-scheduler-*
Current Value: 847 pending jobs
Normal Range: 0-50 pending jobs
```

```
CRITICAL: scheduler.leader.count > 1
Multiple nodes claiming leadership
Node A: datanexus-scheduler-prod-1 (leader since 06:15)
Node B: datanexus-scheduler-prod-2 (leader since 06:22)
```

---

## Timeline

**06:15 UTC** - Scheduler-prod-1 acquired leadership, started processing jobs

**06:20 UTC** - Brief network partition between scheduler nodes and Redis

**06:22 UTC** - Scheduler-prod-2 also acquired leadership (Redis key expired during partition)

**06:25 UTC** - Both nodes now executing jobs simultaneously

**06:28 UTC** - Customer reported duplicate job executions

**06:30 UTC** - Alert fired for pending job backlog

**06:35 UTC** - Jobs completing but dependent jobs not starting

**06:45 UTC** - Some DAG pipelines showing out-of-order execution

---

## Grafana Dashboard Observations

### Leader Election Status
```
Time: 06:00 - 07:00 UTC

scheduler-prod-1: isLeader=true  (continuous)
scheduler-prod-2: isLeader=false (06:00-06:22)
scheduler-prod-2: isLeader=true  (06:22-ongoing)

Both nodes believe they are the leader!
```

### Job Execution Metrics
```
Jobs Started: 1,247
Jobs Completed: 892
Jobs Failed: 127
Jobs Stuck in Pending: 847
Jobs Executed Twice: 53 (should be 0)
```

### DAG Pipeline Execution
```
Pipeline: daily_etl_pipeline
  Step 1 (extract): Completed at 06:32
  Step 2 (transform): Started at 06:28 (BEFORE step 1!)
  Step 3 (load): Pending
  Step 4 (validate): Started at 06:35

Note: Steps running out of dependency order
```

---

## Customer Reports

### DataFlow Industries
> "Our ETL pipeline ran the 'transform' step before 'extract' completed. Now we have corrupt data in our warehouse. The scheduler is supposed to respect dependencies!"

### AnalyticsPro
> "Jobs that were cancelled 2 hours ago are still showing as 'in_progress'. When will they actually stop? Their child tasks are blocking other work."

### ScheduleMax Corp
> "Our daily cron job that's supposed to run at 9 AM EST ran at 9 AM UTC instead. We missed our data refresh window."

---

## Error Logs

### Split-Brain Detection
```
2024-01-17T06:22:05Z [scheduler-prod-2] Leader election: acquired lock
  Note: Node 1 still believes it holds the lock

2024-01-17T06:22:10Z [scheduler-prod-1] Renewing leader lock
  Note: Renewal succeeded because we didn't verify ownership

2024-01-17T06:23:00Z [scheduler-prod-1] Executing job: job_12345
2024-01-17T06:23:00Z [scheduler-prod-2] Executing job: job_12345
  Note: Same job executed by both leaders!
```

### DAG Execution Order
```
2024-01-17T06:28:15Z [DAG] Topological sort completed
  Order: [transform, extract, load, validate]
  Note: Order is WRONG - extract should come before transform

2024-01-17T06:28:20Z [DAG] Starting job: transform
  Dependencies check: passed
  Note: Dependencies check passed but extract hasn't run yet!
```

### Cron Timezone Issue
```
2024-01-17T09:00:00Z [cron] Executing scheduled job: daily_refresh
  Schedule: "0 9 * * *" (intended: 9 AM EST)
  Executed at: 09:00 UTC (4 AM EST)
  Customer timezone setting: "America/New_York"
  Note: Timezone setting was stored but not used in calculation
```

### Job Cancellation Leak
```
2024-01-17T06:40:00Z [job] Cancel requested for job_56789
2024-01-17T06:40:01Z [job] Job marked as cancelled
  Note: Subtasks still running...
  Note: Downstream jobs still waiting on cancelled job
2024-01-17T06:45:00Z [job] Subtask of job_56789 completed
  Note: Nobody received the result
```

---

## Internal Investigation

**@oncall.dev** (07:00):
> The leader election is using a simple SET NX with TTL. During the network partition, the key expired and node 2 acquired it. But node 1 never checked if it still owned the lock before renewing.

**@oncall.dev** (07:10):
> The topological sort is using `unshift` instead of `push`:
> ```javascript
> result.unshift(nodeId);
> ```
> This reverses the order! Dependencies run AFTER their dependents.

**@oncall.sre** (07:15):
> The cycle detection is also broken. We have a DAG with A->B->C->A and it wasn't detected. The algorithm only checks if a node was visited, not if it's currently in the recursion stack.

**@oncall.dev** (07:22):
> Cron jobs are using `new Date()` which returns local time. The configured timezone is stored but never applied when calculating the next run time.

**@oncall.sre** (07:30):
> Job cancellation just removes the job from `runningJobs` but doesn't actually stop the async tasks or cancel downstream dependencies. Those jobs wait forever.

**@oncall.dev** (07:35):
> And the retry backoff has an overflow issue:
> ```javascript
> const delay = this.baseDelay * Math.pow(2, attempt);
> ```
> For attempt > 50, this exceeds MAX_SAFE_INTEGER. `Math.min` with Infinity returns Infinity, so retries wait forever.

---

## Reproduction Steps

### Split-Brain
1. Start two scheduler nodes with Redis leader election
2. Simulate network partition (block Redis traffic to node 1)
3. Wait for TTL expiry (10 seconds)
4. Node 2 acquires leadership
5. Restore network
6. Both nodes now claim leadership

### Wrong DAG Order
1. Create DAG: A -> B -> C (A depends on B, B depends on C)
2. Execute DAG
3. Observe execution order: A, B, C (should be C, B, A)

### Cron Timezone
1. Create cron job with schedule "0 9 * * *"
2. Configure timezone "America/New_York"
3. Observe job executes at 9 AM server time (UTC), not 9 AM EST

---

## Files to Investigate

- `services/scheduler/src/services/dag.js` - DAG execution, topological sort
- Cron scheduler timezone handling
- Leader election implementation
- Job cancellation and cleanup
- Retry policy backoff calculation

---

**Status**: INVESTIGATING
**Assigned**: @platform-team, @scheduler-team
**Priority**: P0 - Data integrity at risk
