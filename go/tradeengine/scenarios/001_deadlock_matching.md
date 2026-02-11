# Incident Report: Matching Engine Deadlock

## Incident Summary

**Severity**: SEV-1
**Status**: Ongoing
**Opened**: 2024-03-15 14:32 UTC
**Services Affected**: Matching Engine, Order Service, Gateway

## Alert Details

```
[CRITICAL] Matching Engine - Request latency > 30s
[CRITICAL] Order Queue Depth > 10,000 (threshold: 1,000)
[WARNING] Gateway WebSocket connections dropping
[WARNING] Goroutine count: 45,000 (normal: ~200)
```

## Timeline

- **14:28 UTC**: Customer reports order stuck in "pending" state for 5+ minutes
- **14:30 UTC**: Additional reports from trading desk - multiple orders not filling
- **14:32 UTC**: PagerDuty alert fires for matching engine latency
- **14:35 UTC**: Order queue depth exceeds 10,000
- **14:40 UTC**: Goroutine count continues climbing
- **14:45 UTC**: Service restart temporarily resolves, issue recurs within 10 minutes

## Symptoms Observed

### Primary Symptoms
1. Orders submitted but never matched, even when matching prices exist
2. Matching engine `/health` endpoint returns 200 but processing appears frozen
3. Goroutine count grows unboundedly
4. Service restarts provide temporary relief (~5-10 minutes)

### Secondary Symptoms
1. Some orders cancel successfully, others hang indefinitely on cancel request
2. CPU usage is low (5-10%) despite high load
3. Memory usage grows slowly over time
4. Stack traces show goroutines blocked on mutex acquire

### Stack Trace Sample

```
goroutine 1847 [semacquire, 142 minutes]:
sync.runtime_SemacquireMutex(0xc0004a2108, 0xc0?)
    /usr/local/go/src/runtime/sema.go:77 +0x25
sync.(*Mutex).lockSlow(0xc0004a2100)
    /usr/local/go/src/sync/mutex.go:171 +0x165
sync.(*Mutex).Lock(...)
    /usr/local/go/src/sync/mutex.go:90
github.com/terminal-bench/tradeengine/internal/matching.(*Engine).CancelOrder(0xc0004a2080, {0x1821340, 0xc000562180}, {{0x12, 0x34, ...}})
    /app/internal/matching/engine.go:161 +0x85

goroutine 1903 [semacquire, 142 minutes]:
sync.runtime_SemacquireMutex(0xc0004a2148, 0xc0?)
    /usr/local/go/src/runtime/sema.go:77 +0x25
sync.(*RWMutex).Lock(0xc0004a2140)
    /usr/local/go/src/sync/rwmutex.go:115 +0x65
github.com/terminal-bench/tradeengine/internal/matching.(*Engine).SubmitOrder(0xc0004a2080, {0x1821340, 0xc000562200}, 0xc0005d4000)
    /app/internal/matching/engine.go:112 +0x4c
```

### Reproduction Pattern

1. High volume of orders and cancellations occurring simultaneously
2. Multiple symbols being traded concurrently
3. Issue more likely when same user has orders on both bid and ask side
4. Always involves concurrent SubmitOrder and CancelOrder operations

## Affected Components

- `internal/matching/engine.go` - Primary suspect based on stack traces
- `pkg/orderbook/book.go` - Order book operations
- Possibly related: message handlers that invoke these methods concurrently

## Metrics Dashboard

```
Metric                          | Before Incident | During Incident
--------------------------------|-----------------|------------------
Orders/sec                      | 1,200           | 0
Avg Match Latency (ms)          | 2.3             | 30,000+
Goroutine Count                 | 180             | 45,000+
Blocked Goroutines              | 0               | ~44,800
CPU Usage                       | 45%             | 8%
Memory Usage                    | 2.1 GB          | 3.8 GB (growing)
Active Mutex Waiters            | 0-2             | 1,000+
```

## Investigation Notes

1. The stack traces consistently show two different lock acquisition patterns
2. Some goroutines are waiting on `booksMu` while holding `ordersMu`
3. Other goroutines appear to wait on `ordersMu` while holding `booksMu`
4. The `Engine.processMu` mutex also appears in some blocked stacks

## Questions to Investigate

1. What is the lock acquisition order in SubmitOrder vs CancelOrder?
2. Are there any error paths that might not release locks?
3. Why does the goroutine count keep growing even when processing is blocked?
4. What happens to the processing goroutine when the engine appears frozen?

## Temporary Mitigation

- Restart matching engine service (provides ~5-10 min relief)
- Reduce order submission rate via gateway rate limiting
- Disable cancel functionality temporarily (not acceptable for production)

## Runbook Reference

- [Matching Engine Restart Procedure](../docs/runbooks/matching-restart.md)
- [Order Queue Drain Procedure](../docs/runbooks/order-drain.md)
