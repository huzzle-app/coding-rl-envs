# Scenario 05: Market Data Service Overwhelmed on Cache Miss

**Severity**: P1 (Critical)
**Reported By**: SRE/On-Call
**Date**: Wednesday, 2:47 PM EST

---

## Incident Summary

The market-data service experienced a cascading failure when Redis cache expired for popular symbols. CPU spiked to 100%, response times exceeded 30 seconds, and downstream services (orders, matching) began failing due to inability to get current prices.

## Symptoms

### Primary Complaint

PagerDuty Alert:
```
[CRITICAL] market-data-service: Response time p99 > 30s
[CRITICAL] market-data-service: CPU > 95% sustained 5min
[WARNING] orders-service: Dependency failure (market-data)
[WARNING] matching-engine: Price lookup timeout
[CRITICAL] redis: Connection pool exhausted
```

### Observed Behaviors

1. **Cache expiration causes simultaneous requests**:
   ```
   [14:45:00.000] Cache TTL expired for AAPL, MSFT, GOOGL (all set at same time)
   [14:45:00.001] GET /quotes/AAPL -> cache miss
   [14:45:00.002] GET /quotes/AAPL -> cache miss
   [14:45:00.003] GET /quotes/AAPL -> cache miss
   [...50 more requests for AAPL in 100ms...]
   [14:45:00.100] All 53 requests hitting external data source
   ```

2. **Thundering herd on popular symbols**:
   ```
   Symbol  | Requests/sec | Cache Status | Data Source Hits
   --------|--------------|--------------|------------------
   AAPL    | 850          | MISS         | 850 (should be 1)
   MSFT    | 720          | MISS         | 720 (should be 1)
   NVDA    | 680          | MISS         | 680 (should be 1)
   SPY     | 1200         | MISS         | 1200 (should be 1)
   ```

3. **Hot key concentration in Redis**:
   ```
   Redis SLOWLOG shows:
   - HSET market_data:AAPL ... (blocked 450ms)
   - HGET market_data:AAPL (blocked 380ms)
   - All operations on same key serialized
   ```

4. **WebSocket connections pile up on single server**:
   ```
   market-data-1: 45,000 connections (AAPL, MSFT, GOOGL)
   market-data-2: 3,200 connections (less popular symbols)
   market-data-3: 2,800 connections (less popular symbols)

   Expected: ~17,000 connections per server (even distribution)
   ```

### Timeline

| Time | Event |
|------|-------|
| 14:30:00 | Cache populated with 60-second TTL |
| 14:31:00 | All entries expire simultaneously |
| 14:31:00.001 | Cache miss storm begins |
| 14:31:00.500 | External data source rate limited |
| 14:31:02 | CPU at 100%, response times spike |
| 14:31:05 | Connection pool exhausted |
| 14:31:10 | Downstream services timing out |
| 14:35:00 | Manual intervention, flush cache, restart |

## Impact

- **Trading**: 4-minute window where orders couldn't get price data
- **Users**: Real-time quotes froze, WebSocket disconnections
- **Revenue**: Estimated $50K in missed trading fees
- **SLA**: Breached 99.9% uptime target for the month

## Initial Investigation

### What We've Ruled Out
- DDoS attack (traffic patterns match normal usage)
- External data source outage (responded, just rate limited us)
- Network issues (inter-service latency normal)
- Memory leak (heap usage normal)

### Suspicious Observations

1. **Fixed TTL for all cache entries**:
   ```python
   CACHE_TTL = 60  # All entries expire at same time
   # No jitter/randomization
   ```

2. **No request coalescing for cache misses**:
   ```python
   # When cache miss, each request independently fetches
   # No deduplication of in-flight requests
   ```

3. **Cache update race condition (TOCTTOU)**:
   ```
   Request 1: Check cache -> MISS
   Request 1: Fetch from source
   Request 2: Check cache -> MISS (still empty)
   Request 2: Fetch from source
   Request 1: Write to cache
   Request 2: Write to cache (overwrites, wasted work)
   ```

4. **Hot key problem in Redis**:
   - All AAPL data in single hash
   - 1000+ concurrent reads/writes to same key
   - Redis single-threaded, serializes all operations

5. **WebSocket routing doesn't load balance**:
   ```python
   # Clients connecting to /ws/quotes/AAPL all go to same server
   # No consistent hashing or round-robin
   ```

### Relevant Code Paths
- `services/market-data/main.py` - get_quote, cache logic
- `services/market-data/main.py` - WebSocket handling
- `services/market-data/main.py` - CACHE_TTL configuration
- `shared/clients/base.py` - request coalescing (disabled by default)

## Reproduction Steps

### Cache Stampede Test
1. Configure short TTL (5 seconds) for testing
2. Populate cache for AAPL
3. Wait for expiration
4. Simultaneously send 100 requests for AAPL quote
5. Expected: 1 cache miss triggers fetch, 99 wait for result
6. Actual: 100 cache misses, 100 fetches to data source

### Hot Key Test
1. Monitor Redis SLOWLOG
2. Subscribe 1000 clients to AAPL WebSocket feed
3. Observe all clients hitting same Redis key
4. Expected: Distributed across multiple keys/shards
5. Actual: All operations on single key, serialized

### Fixed TTL Test
1. Watch cache expiration times
2. Expected: Entries expire at different times (jittered)
3. Actual: All entries set at same time expire together

## Questions for Investigation

- Is there TTL jitter to prevent synchronized expiration?
- What happens on cache miss - do concurrent requests wait or all fetch?
- How are WebSocket connections distributed across servers?
- Is there a request coalescing mechanism for duplicate in-flight requests?
- How is the Redis key structure designed for hot symbols?

---

**Status**: Unresolved
**Assigned**: Platform/Infrastructure Team
**SLA**: 2 hours (P1)
