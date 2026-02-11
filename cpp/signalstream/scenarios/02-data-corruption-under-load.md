# Incident Report: Data Corruption Under High Load

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-20 14:30 UTC
**Acknowledged**: 2024-01-20 14:33 UTC
**Team**: Data Platform Engineering

---

## Alert Details

```
CRITICAL: Data integrity check failed - checksum mismatch
Service: signalstream-storage-prod
Metric: data_corruption_events
Threshold: >0 in 5 minutes
Current Value: 47
```

## Customer Report (QuantumTrading Ltd - Enterprise)

> We're seeing corrupted financial data in our real-time trading stream. Prices are showing impossible values (negative prices, NaN), and our risk calculations are failing validation. This is causing our automated trading systems to halt with safety violations. We need this fixed IMMEDIATELY.

### Reported Symptoms

1. **Corrupted price data**: Occasionally see prices like `$-0.00` or `$NaN`
2. **Duplicate events**: Same trade event processed multiple times
3. **Missing events**: Some events never arrive at downstream consumers
4. **Garbled strings**: Transformation output contains garbage characters
5. **Crashes under load**: Services crash when processing high-volume streams

---

## Technical Analysis

### ThreadSanitizer Report (Ingest Service)

```
==================
WARNING: ThreadSanitizer: data race (pid=12345)
  Write of size 8 at 0x7f3c00012340 by thread T7:
    #0 IngestBuffer::append() src/services/ingest/buffer.cpp:89
    #1 IngestService::processMessage() src/services/ingest/ingest.cpp:142

  Previous read of size 8 at 0x7f3c00012340 by thread T3:
    #0 IngestBuffer::flush() src/services/ingest/buffer.cpp:112
    #1 IngestService::flushWorker() src/services/ingest/ingest.cpp:201

  Location is heap block of size 1024 at 0x7f3c00012000
==================
```

### Memory Corruption Evidence

```
=================================================================
==23456==ERROR: AddressSanitizer: heap-use-after-free
READ of size 8 at 0x604000001234 by thread T5

    #0 0x555556789abc in ConnectionPool::getConnection() src/shared/pool.cpp:67
    #1 0x555556789def in StorageService::persist() src/services/storage/storage.cpp:134

0x604000001234 is located 16 bytes inside of 128-byte region freed by thread T2

    #0 0x7f3c12345678 in operator delete(void*)
    #1 0x555556780123 in ConnectionPool::returnConnection() src/shared/pool.cpp:89

SUMMARY: AddressSanitizer: heap-use-after-free
```

### Condition Variable Issues

Ingest service logs show sporadic issues with data processing:

```
2024-01-20T14:32:15.123Z [ingest] Waiting for data availability...
2024-01-20T14:32:15.124Z [ingest] Woke up, checking condition...
2024-01-20T14:32:15.124Z [ingest] Data not available, but we processed anyway?!
2024-01-20T14:32:15.125Z [ERROR] Processing null data pointer
```

The log suggests the service is waking from a condition variable wait but the predicate hasn't been satisfied (spurious wakeup not handled).

### Lock-Free Queue Issues

High-contention scenarios show ABA problems:

```
2024-01-20T14:35:00.001Z [router] TaskQueue head: 0x1234 -> 0x5678
2024-01-20T14:35:00.002Z [router] CAS succeeded, but data looks wrong
2024-01-20T14:35:00.002Z [ERROR] Task data corrupted: expected job_id=100, got job_id=0
2024-01-20T14:35:00.003Z [router] Detected potential ABA problem in lock-free queue
```

### Reader Starvation

Router service shows readers blocked for extended periods:

```
2024-01-20T14:40:00.000Z [router] Thread-5 waiting for read lock...
2024-01-20T14:40:05.000Z [router] Thread-5 still waiting (5s)...
2024-01-20T14:40:10.000Z [router] Thread-5 still waiting (10s)...
2024-01-20T14:40:15.000Z [router] Thread-5 acquired read lock after 15 seconds
2024-01-20T14:40:15.001Z [WARN] Reader starvation detected - writers continuously preempting
```

### Fair RWLock Issues

```
2024-01-20T14:42:00.000Z [shared] FairRWLock: writer_waiting=true
2024-01-20T14:42:00.001Z [shared] Reader thread acquired lock despite writer waiting
2024-01-20T14:42:00.002Z [shared] Another reader acquired lock
2024-01-20T14:42:00.003Z [shared] Writer starved for 50+ reader acquisitions
```

The "fair" read-write lock doesn't appear to be honoring writer priority when `writer_waiting` is set.

### Spinlock Contention Collapse

Under high load, CPU usage spikes to 100% with no progress:

```
CPU Profile (top functions during incident):
  45.2%  Spinlock::lock()
  38.7%  Spinlock::lock()  (different call site)
   8.1%  [kernel] schedule
   5.3%  Spinlock::lock()  (yet another call site)
   2.7%  actual work
```

### String View Dangling Reference

```
2024-01-20T14:45:00.000Z [transform] Processing message: "AAPL:150.25:BUY:1000"
2024-01-20T14:45:00.001Z [transform] Extracted symbol: "AAPL"
2024-01-20T14:45:00.002Z [transform] After transformation, symbol: "▒▒▒▒" (garbage)
2024-01-20T14:45:00.003Z [ERROR] Invalid symbol in transformed message
```

### Iterator Invalidation

Storage service crashes during concurrent operations:

```
2024-01-20T14:48:00.000Z [storage] Thread-8: Iterating over data map...
2024-01-20T14:48:00.001Z [storage] Thread-9: Inserting new record...
2024-01-20T14:48:00.002Z [FATAL] Iterator invalidated during iteration
terminate called after throwing an instance of 'std::runtime_error'
```

---

## Performance Impact

| Metric | Normal | During Incident |
|--------|--------|-----------------|
| P99 Latency | 15ms | 850ms |
| Error Rate | 0.01% | 12.3% |
| Throughput | 50k msg/s | 8k msg/s |
| CPU Usage | 45% | 98% |

---

## Atomic Memory Ordering Issues

Valgrind/Helgrind reports:

```
==34567== Possible data race during read of size 8 at 0x12345678
==34567==    at 0x555556666: Counter::load() (atomic_counter.cpp:45)
==34567==    This conflicts with a previous write of size 8
==34567==    at 0x555556777: Counter::store() (atomic_counter.cpp:52)
==34567==
==34567== Note: Using memory_order_relaxed for inter-thread synchronization
==34567== Hint: Consider using memory_order_acquire/memory_order_release
```

---

## False Sharing Evidence

Performance counters show cache line bouncing:

```
perf stat output:
  15,234,567,890  L1-dcache-load-misses
   8,765,432,100  cache-references
   7,654,321,000  cache-misses   (87.5% of all cache refs)

Note: Adjacent atomic counters appear to be on same cache line
Struct layout shows counters separated by only 8 bytes
```

---

## Questions for Investigation

1. Why is the ingest buffer accessed without synchronization?
2. Why does the connection pool return a pointer that gets freed?
3. Why is the condition variable waking without the predicate being true?
4. What causes the ABA problem in the lock-free task queue?
5. Why are readers not respecting the `writer_waiting` flag?
6. Why does the spinlock have no backoff mechanism?
7. Why does string_view hold a dangling reference after function returns?
8. How can iterators be invalidated during concurrent insert?

---

## Partial Memory Comparison Failure

```
2024-01-20T14:50:00.000Z [storage] Comparing records for equality...
2024-01-20T14:50:00.001Z [storage] Record A: {id=100, value=50.0, ...}
2024-01-20T14:50:00.001Z [storage] Record B: {id=100, value=50.0, ...}
2024-01-20T14:50:00.002Z [storage] memcmp result: NOT EQUAL (expected equal)
2024-01-20T14:50:00.002Z [WARN] Records with identical field values compare as different
```

Records that appear identical are failing equality checks.

---

**Status**: INVESTIGATING
**Impact**: High-value trading customers unable to process real-time data
**Assigned**: @data-platform-team, @sre-team
