# Incident Report: Memory Leak in Web Workers

## Datadog Alert

**Severity**: High (P2)
**Triggered**: 2024-01-22 06:30 UTC
**Acknowledged**: 2024-01-22 06:45 UTC
**Team**: Platform Engineering

---

## Alert Details

```
WARNING: taskforge-web-prod memory usage trending upward
Metric: container_memory_working_set_bytes
Pods: taskforge-web-prod-{1,2,3,4}
Pattern: Steady increase ~50MB/hour
Current: 3.2GB average (started at 1.8GB after last deploy)
Threshold: Alert at 4GB, OOM at 5GB
Time to OOM: ~36 hours at current rate
```

## Timeline

**Day 1 - 00:00 UTC**: Deployed v3.2.5 with new search optimizations

**Day 1 - 06:30 UTC**: Initial memory alert triggered, dismissed as post-deploy warmup

**Day 1 - 18:00 UTC**: Memory at 2.4GB, ops noticed steady growth pattern

**Day 2 - 06:30 UTC**: Memory at 3.2GB, alert re-triggered, investigation started

**Day 2 - 12:00 UTC**: Test pod allowed to grow to 4.8GB before manual restart

**Day 2 - 12:05 UTC**: Post-restart memory at 1.6GB, immediately begins growing again

## Memory Profile Analysis

### Heap Dump Analysis (memory_profiler gem)

```
Top 10 memory allocations by retained objects:

1. Hash objects: 847,293 instances (was 12,000 at startup)
   Source: NotificationService#user_preferences_cache

2. Array objects: 234,891 instances (was 8,000 at startup)
   Source: SearchService default argument accumulation

3. String objects: 189,234 instances
   Source: Various memoization patterns

Largest retained objects by size:
  NotificationService @user_preferences_cache: 412MB
  TaskService @@default_options mutation chain: 89MB
```

### Growth Pattern
```
Memory growth correlates with:
- User search activity (r=0.82)
- Notification delivery volume (r=0.91)
- Unique user sessions (r=0.78)

Does NOT correlate with:
- Request rate
- Database query count
- Background job count
```

## Slack Thread

**#eng-platform** - January 22, 2024

**@sre.james** (06:50):
> Memory leak confirmed. All web pods growing at same rate. Looks like something is caching data without eviction.

**@dev.sandra** (07:15):
> Ran memory_profiler in staging. There's a `@user_preferences_cache` hash in NotificationService that grows without bound. Every user who receives a notification gets added, but entries are never removed.

**@dev.tom** (07:25):
> That explains the correlation with notification volume. But I'm also seeing something weird in SearchService. Looking at the method signatures...

**@dev.sandra** (07:32):
> Found another issue - there's a class variable in TaskService that gets mutated. `@default_options` starts as a shared hash, and `@options = self.class.default_options` gives every instance a reference to the SAME hash. Mutations accumulate.

**@dev.tom** (07:40):
> SearchService has `def search(options = {})` and then mutates `options` internally. Ruby reuses the same default hash object across calls, so it grows with each search.

**@sre.james** (07:45):
> So we have:
> 1. Unbounded notification preferences cache
> 2. Shared mutable class variable in TaskService
> 3. Mutable default argument in SearchService
>
> All classic Ruby memory leak patterns. Going to need fixes for all three.

**@dev.sandra** (07:50):
> Also seeing potential issues with the singleton pattern in NotificationService. `@@instance` with memoized state means the instance lives forever and accumulates data.

## Application Logs

```
# No explicit errors, but patterns visible:

2024-01-22T06:30:12Z [Rails] INFO: NotificationService cache size: 45,892 entries
2024-01-22T06:31:12Z [Rails] INFO: NotificationService cache size: 45,923 entries
2024-01-22T06:32:12Z [Rails] INFO: NotificationService cache size: 45,967 entries
# Cache only grows, never shrinks

2024-01-22T06:35:00Z [Rails] WARN: TaskService default_options has 12,847 keys (expected 2)
# Options hash being polluted with additional keys
```

## Customer Impact

- Gradual increase in response times as memory pressure grows
- Occasional request timeouts near OOM threshold
- Unpredictable pod restarts during high-traffic periods

## Questions for Investigation

1. Is the notification preferences cache ever cleared?
2. Are there other unbounded caches in the codebase?
3. Which methods have mutable default arguments?
4. Are there other class variables being mutated?

## Files to Investigate

Based on memory profiler output:
- `app/services/notification_service.rb` - User preferences cache
- `app/services/task_service.rb` - Class variable mutation
- `app/services/search_service.rb` - Default argument mutation
- Any singleton patterns in service classes

---

**Status**: INVESTIGATING
**Assigned**: @dev.sandra, @dev.tom
**Workaround**: Scheduled pod restarts every 12 hours until fix deployed
