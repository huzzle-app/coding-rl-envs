# Grafana Alert: Database Connection Pool Exhaustion

## Alert Details

**Alert Name**: PostgreSQL Connection Limit Reached
**Severity**: Critical
**Firing Since**: 2024-01-21 15:42 UTC
**Dashboard**: TalentFlow Infrastructure > Database

---

## Alert Configuration

```yaml
alert: PostgresConnectionLimitReached
expr: pg_stat_activity_count{datname="talentflow"} >= pg_settings_max_connections * 0.9
for: 2m
labels:
  severity: critical
annotations:
  summary: "Database connections approaching limit"
  description: "Active connections {{ $value }} at 90%+ of max (100)"
```

## Current Metrics

| Metric | Value | Threshold |
|--------|-------|-----------|
| Active Connections | 92 | 100 (max) |
| Idle Connections | 3 | - |
| Waiting Queries | 47 | - |
| Connection Wait Time | 8.2s avg | <100ms |
| Failed Connections (5m) | 234 | - |

---

## Error Logs from Application

```
2024-01-21T15:42:14Z ERROR django.db.utils.OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections
2024-01-21T15:42:15Z ERROR Request failed path=/api/v1/candidates/ error="could not connect to server: connection refused"
2024-01-21T15:42:16Z ERROR django.db.utils.OperationalError: connection pool exhausted
2024-01-21T15:42:18Z WARNING Connection wait timeout exceeded for query: SELECT * FROM candidates...
2024-01-21T15:42:20Z ERROR Request failed path=/api/v1/analytics/reports/ error="connection pool exhausted"
...
[234 similar errors in the past 5 minutes]
```

---

## PostgreSQL `pg_stat_activity` Analysis

```sql
SELECT state, count(*), avg(age(now(), query_start)) as avg_duration
FROM pg_stat_activity
WHERE datname = 'talentflow'
GROUP BY state;
```

Results:
```
   state   | count | avg_duration
-----------+-------+--------------
 active    |    15 | 00:00:01.234
 idle      |    77 | 00:12:45.678  # <-- Most connections idle for 12+ minutes!
 idle in t |     3 | 00:02:15.123
```

**Observation**: 77 connections are "idle" but held open for over 12 minutes. These should have been released.

---

## Investigation

### Slack Thread: #eng-platform

**@sre.kim** (15:50):
> We're hitting connection pool limits. 92 out of 100 connections in use, but most are idle. Something is holding connections without releasing them.

**@dev.marcus** (15:55):
> Checking Django database settings... Found something. `CONN_MAX_AGE` is set to `None`.

**@sre.kim** (15:58):
> What does that mean?

**@dev.marcus** (16:00):
> `CONN_MAX_AGE=None` means connections are kept open indefinitely - they never age out. Combined with `CONN_HEALTH_CHECKS=False`, we're not checking if connections are stale before reusing them.

**@dev.sarah** (16:05):
> So connections are being created, used once, then held forever in "idle" state?

**@dev.marcus** (16:08):
> Exactly. Under load, we keep creating new connections because the pool thinks all connections are "in use" (they're actually idle but not released). Eventually we hit PostgreSQL's max_connections.

**@sre.kim** (16:12):
> What should these settings be?

**@dev.marcus** (16:15):
> `CONN_MAX_AGE` should be something like 60 (seconds) - connections older than that get closed. And `CONN_HEALTH_CHECKS=True` means we verify connections are alive before using them.

---

## Configuration Analysis

### Current Settings (PROBLEMATIC)
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'talentflow',
        # ...
        'CONN_MAX_AGE': None,           # Never close connections!
        'CONN_HEALTH_CHECKS': False,     # Don't check if connections are alive
    }
}
```

### Connection Lifecycle Issue
1. Request comes in, Django gets connection from pool
2. Request completes, connection marked "idle" but kept in pool
3. Connection sits idle for hours/days (CONN_MAX_AGE=None means never expire)
4. During high load, new requests can't get connections
5. Django creates MORE connections instead of reusing idle ones
6. Eventually hits PostgreSQL max_connections (100)

---

## Redis Connection Leak (Secondary Issue)

While investigating, we also found connection leaks in the analytics caching layer:

```python
# From Sentry error tracking:
redis.exceptions.ConnectionError: Too many connections
  File "apps/analytics/caching.py", line 204
    conn = redis.from_url(redis_url)
    # Creating new connection every time!
```

The `QueryResultCache` class creates new Redis connections without pooling:

```
Redis Connection Count Over Time:
15:00  45 connections
15:15  78 connections
15:30  112 connections
15:45  156 connections  # Steadily climbing!
16:00  192 connections
```

---

## Impact Assessment

- **API Availability**: 15% of requests failing with connection errors
- **Response Times**: P99 latency increased from 500ms to 12s
- **Affected Features**: All database-backed operations
- **User Reports**: "Page won't load", "Timeout errors", "Please try again later"

---

## Customer Complaints

### Zendesk Ticket #92456
> Every time I try to load the candidate list, I get a "Service Unavailable" error. This started about an hour ago. We have interviews scheduled this afternoon!

### Zendesk Ticket #92461
> Analytics reports are timing out. We need the weekly pipeline report for our 3 PM exec meeting.

### Zendesk Ticket #92478
> The entire system is unusable. We're a 500-person company and everyone is affected.

---

## Concurrent Application Race Condition

Related investigation found that under high load, the application limit check for jobs has a race condition:

```
Job ID: 12345
max_applications: 50

Concurrent applications received:
- 15:42:01.123 - Application from candidate_a - Accepted (count was 49)
- 15:42:01.124 - Application from candidate_b - Accepted (count was 49)
- 15:42:01.125 - Application from candidate_c - Accepted (count was 49)
- 15:42:01.126 - Application from candidate_d - Accepted (count was 49)
... (5 more in same millisecond)

Final count: 58 applications (limit was 50!)
```

The `apply_to_job` function checks the count but doesn't lock the row, allowing concurrent requests to bypass the limit.

---

## Files to Investigate

- `talentflow/settings/base.py` or `talentflow/settings/development.py` - Database connection settings
- `apps/analytics/caching.py` - Redis connection management
- `apps/jobs/matching.py` - Application limit race condition

---

## Immediate Mitigation

1. Restart application pods to release stuck connections
2. Temporarily increase PostgreSQL max_connections to 150

## Root Cause Fixes Needed

1. Set `CONN_MAX_AGE` to a reasonable value (e.g., 60 seconds)
2. Enable `CONN_HEALTH_CHECKS`
3. Fix Redis connection pooling in analytics caching
4. Add row-level locking to application limit checks

---

**Status**: ACTIVE INCIDENT
**Assigned**: @sre.kim, @dev.marcus
**Incident Commander**: @eng.lead
**Next Update**: 2024-01-21 17:00 UTC
