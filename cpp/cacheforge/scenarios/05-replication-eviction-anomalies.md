# Support Ticket: Replication Lag and Eviction Failures

## Zendesk Ticket #52341

**Priority**: High
**Customer**: DataStream Inc. (Enterprise Tier)
**Account Value**: $180,000 ARR
**CSM**: Robert Chen
**Created**: 2024-01-22 11:20 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We're experiencing two related issues with our CacheForge cluster:
>
> 1. Replication to our DR site shows empty keys in the logs, making debugging impossible
> 2. Eviction isn't working properly - cache keeps growing beyond the configured limit
>
> These issues are causing us to manually intervene daily. We need these fixed ASAP.

---

## Issue 1: Empty Keys in Replication Logs

### Customer Logs

```
2024-01-22T08:15:23Z DEBUG Enqueued replication event for key:
2024-01-22T08:15:23Z DEBUG Enqueued replication event for key:
2024-01-22T08:15:23Z DEBUG Enqueued replication event for key:
2024-01-22T08:15:24Z DEBUG Sending batch of 3 events
2024-01-22T08:15:24Z DEBUG Enqueued replication event for key:
2024-01-22T08:15:24Z DEBUG Enqueued replication event for key:
```

### Expected Behavior

```
2024-01-22T08:15:23Z DEBUG Enqueued replication event for key: user:12345
2024-01-22T08:15:23Z DEBUG Enqueued replication event for key: session:abc123
2024-01-22T08:15:23Z DEBUG Enqueued replication event for key: cache:homepage
```

### Customer Analysis

> "The replication is actually working - data does arrive at the DR site. But the logs show empty keys, which makes it impossible to debug when things go wrong. We can't correlate which keys are being replicated."

---

## Issue 2: Eviction Not Triggering

### Configuration

```yaml
max_memory: 8GB
eviction_policy: lru
max_keys: 10000000
```

### Observed Behavior

```
$ cacheforge-cli INFO memory
used_memory: 9.2GB
maxmemory: 8GB
evicted_keys: 0
keys: 12,345,678
```

The cache is 1.2GB over the configured limit, and `evicted_keys` shows zero evictions have occurred.

### Customer Monitoring Data

```
Time        | Memory Used | Key Count    | Evictions/min
------------|-------------|--------------|---------------
08:00       | 7.8 GB      | 9,800,000    | 0
09:00       | 8.1 GB      | 10,100,000   | 0  <-- should have started evicting
10:00       | 8.5 GB      | 10,600,000   | 0
11:00       | 9.2 GB      | 12,345,678   | 0
```

The eviction callback is registered but never fires, even when the key count exceeds `max_keys`.

---

## Internal Investigation

### Slack Thread: #cache-eng

**@dev.marcus** (11:45):
> Looking at the replication log issue. Found something weird in `replicator.cpp`:

```cpp
void Replicator::enqueue(ReplicationEvent event) {
    event.sequence = next_sequence();
    std::lock_guard lock(queue_mutex_);
    event_queue_.push(std::move(event));  // event is moved here
    spdlog::debug("Enqueued replication event for key: {}", event.key);  // accessing after move!
}
```

**@dev.marcus** (11:48):
> After `std::move(event)`, the event object is in a "valid but unspecified state". The key string is likely empty or garbage. This is a classic use-after-move bug.

**@dev.sarah** (11:55):
> That explains the empty keys. What about the eviction issue?

**@dev.marcus** (12:05):
> Looking at the eviction trigger in hashtable.cpp:

```cpp
if (size_.load(std::memory_order_relaxed) > max_size_ && eviction_callback_) {
    eviction_callback_(key);
}
```

**@dev.marcus** (12:08):
> This uses `memory_order_relaxed` for reading the size. The problem is relaxed ordering doesn't provide synchronization - the eviction thread might see a stale (smaller) size value and not trigger eviction.

**@dev.sarah** (12:15):
> Also, I noticed in expiry.h that the condition variable notification might be broken:

```cpp
void ExpiryManager::set_expiry(const std::string& key, std::chrono::seconds ttl) {
    {
        std::lock_guard lock(mutex_);
        entries_[key] = {Clock::now() + ttl};
    }  // mutex released here
    cv_.notify_one();  // notifying without holding mutex!
}
```

**@dev.sarah** (12:18):
> If the expiry thread is checking the predicate and about to sleep, but hasn't called `wait()` yet, this `notify_one()` is lost. The thread sleeps for the full interval even though a new key with short TTL was just added.

---

## Additional Observations

### Replication Sequence Counter

The customer also mentioned seeing occasional wraparound issues with sequence numbers after very long uptime:

```
2024-01-22T10:45:00Z WARN Unexpected sequence number: -9223372036854775808
```

This suggests signed integer overflow in the sequence counter.

### Expiry Thread Delays

Keys with short TTLs sometimes persist beyond their expiration:

```
$ cacheforge-cli SET temp_key value EX 5
OK
$ sleep 10
$ cacheforge-cli GET temp_key
"value"  # Should have expired 5 seconds ago!
```

This correlates with the condition variable notification issue.

---

## Reproduction Steps

### Empty replication keys:
1. Enable debug logging
2. Perform any SET operation
3. Observe replication log shows empty key

### Eviction failure:
1. Configure `max_keys: 100`
2. Insert 200 keys
3. Observe no evictions, key count reaches 200

### Expiry delay:
1. SET key with 1-second TTL
2. Wait 10 seconds
3. Key may still exist (intermittent)

---

## Impact Assessment

- **Replication debugging**: Impossible to trace data flow to DR site
- **Memory management**: OOM risk as cache grows unbounded
- **Data consistency**: Expired keys serving stale data

---

## Files to Investigate

Based on the analysis:
- `src/replication/replicator.cpp` - Use-after-move bug, sequence overflow
- `src/storage/hashtable.h` - Relaxed memory ordering on size counter
- `src/storage/expiry.h` - Condition variable notification outside lock

---

**Status**: INVESTIGATING
**Assigned**: @cache-platform-team
**SLA**: 24 hours (Enterprise tier)
