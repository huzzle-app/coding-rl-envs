# Incident Report: Cache Stampede During Popular Release

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-16 20:00 UTC
**Acknowledged**: 2024-02-16 20:02 UTC
**Team**: Platform Engineering
**Duration**: 45 minutes

---

## Alert Details

```
CRITICAL: streaming-service latency spike
Metric: p99_latency
Threshold: >2000ms for 3 minutes
Current Value: 8,432ms

CRITICAL: origin_requests_per_second
Threshold: >10,000
Current Value: 87,234

CRITICAL: postgresql_connections
Threshold: >450 (of 500 max)
Current Value: 498
```

## Timeline

**20:00 UTC** - New Marvel movie "Quantum Nexus" became available for streaming

**20:01 UTC** - Cache TTL expired for movie metadata (standard 5-minute TTL)

**20:02 UTC** - Origin request rate spiked from 500/s to 87,000/s

**20:03 UTC** - PostgreSQL connection pool exhausted, queries timing out

**20:05 UTC** - streaming-service pods entering crash loop

**20:08 UTC** - Circuit breakers opened, returning 503 to all video requests

**20:15 UTC** - Manually scaled origin database to 4x capacity

**20:25 UTC** - Connection pool pressure reduced, services recovering

**20:45 UTC** - Full service restoration

---

## What Happened

At exactly 20:00 UTC, our most anticipated movie release of the quarter went live. Within seconds:

1. 250,000 concurrent users attempted to access the movie
2. Cache entries for movie metadata expired simultaneously
3. ALL 250,000 requests attempted to fetch from origin database
4. Database connection pool (500 connections) instantly exhausted
5. Cascading failures across the streaming infrastructure

---

## Internal Slack Thread

**#incident-20240216** - February 16, 2024

**@sre-alex** (20:05):
> We're in full stampede. Every request is hitting origin. Cache isn't protecting us at all.

**@sre-alex** (20:07):
> Origin metrics:
> ```
> Normal: 500 req/s to origin
> Current: 87,234 req/s to origin
> ```
> That's 175x normal load hitting the database directly.

**@eng-priya** (20:10):
> The cache should be preventing this. Why isn't `getOrCompute` coalescing requests?

**@sre-alex** (20:12):
> Looking at the code... there's no locking. When cache misses, ALL concurrent requests call the compute function. Classic cache stampede.

**@eng-priya** (20:15):
> Also found that all cache entries for the movie catalog expired at exactly the same time. There's no TTL jitter - we set everything to 300 seconds and they all expire together.

**@sre-alex** (20:18):
> That explains it. 5 minutes ago was 19:55 when the content was first cached during pre-release testing. 300 seconds later = 20:00 = release time = boom.

**@eng-mike** (20:22):
> I'm seeing another issue. The hot movie metadata is always going to the same cache node. Node redis-cache-3 is at 99% CPU while others are at 15%.

**@sre-alex** (20:25):
> That's the consistent hashing not spreading hot keys. Popular content all hashes to the same node.

---

## Grafana Dashboard

### Origin Request Rate
```
19:55  |                                              ___
19:56  |                                             |   |
19:57  |                                             |   |
19:58  |                                             |   |
19:59  |                                             |   |
20:00  |___________________________________________|   |_____
       0      20k     40k     60k     80k    100k

Peak: 87,234 req/s at 20:02
```

### Cache Hit Rate
```
Normal baseline: 99.2%
During incident: 0.3%
Recovery: 94.1%
```

### Database Connections
```
19:59  |  ████████████████████░░░░░░░░░░░░░░░░░░░░  420/500
20:00  |  ████████████████████████████████████████  500/500 (EXHAUSTED)
20:01  |  ████████████████████████████████████████  500/500 + 47,234 waiting
20:02  |  ████████████████████████████████████████  500/500 + timeouts
```

### Cache Node CPU Distribution
```
redis-cache-1:  15% CPU
redis-cache-2:  18% CPU
redis-cache-3:  99% CPU  <-- all hot keys here
redis-cache-4:  12% CPU
redis-cache-5:  14% CPU
```

---

## Root Cause Analysis

Three issues combined to create this incident:

### 1. Cache Stampede (No Request Coalescing)
When cache entry expires, the code does:
```
1. Check cache -> miss
2. Call computeFn() to fetch from origin
3. Store result in cache
```

With 250,000 concurrent requests and no locking, ALL requests execute step 2 simultaneously.

### 2. No TTL Jitter
All cache entries for movie catalog use fixed 300-second TTL. When set at the same time, they all expire at the same instant, causing synchronized cache misses.

Expected: TTL = 300s +/- 10% random jitter
Actual: TTL = 300s exactly for all entries

### 3. Hot Key Concentration
Consistent hashing puts all requests for the same key on the same cache node. For extremely popular content, one node becomes a bottleneck while others sit idle.

---

## Impact Assessment

- **Users Affected**: ~250,000 concurrent viewers
- **Error Rate**: 78% of requests failed with 503 during peak
- **Revenue Impact**: Estimated $45,000 in refund requests
- **Brand Impact**: Trending #MediaFlowDown on Twitter
- **SLA Breach**: 99.9% uptime SLA violated

---

## Attempted Mitigations

| Time | Action | Result |
|------|--------|--------|
| 20:06 | Increased cache TTL to 1 hour | No immediate effect (cache already cold) |
| 20:10 | Scaled up database to 4x | Helped reduce connection pressure |
| 20:15 | Manually warmed cache with movie data | Gradual recovery |
| 20:20 | Added additional cache nodes | Didn't help (hot key still on one node) |

---

## Reproduction Steps (for testing)

1. Set up cache with 5-minute TTL, no jitter
2. Warm cache with popular content metadata
3. Wait for cache expiration
4. Simulate 10,000+ concurrent requests for same content
5. Observe all requests hitting origin simultaneously

---

## Files to Investigate

- `services/streaming/src/services/cache.js` - Cache manager, getOrCompute logic
- TTL jitter implementation (or lack thereof)
- Distributed cache hot key handling
- Request coalescing / singleflight pattern

---

**Status**: RESOLVED (mitigated)
**Root Cause**: Not fixed (needs code changes)
**Post-Mortem**: Scheduled for 2024-02-19
**Action Items**:
1. Implement request coalescing
2. Add TTL jitter
3. Implement hot key spreading
