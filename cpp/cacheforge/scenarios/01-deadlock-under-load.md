# Incident Report: Server Hangs Under High Load

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-18 14:27 UTC
**Acknowledged**: 2024-01-18 14:31 UTC
**Team**: Cache Infrastructure

---

## Alert Details

```
CRITICAL: cacheforge-prod-01 health check timeout
Host: cacheforge-prod-01.us-west-2.internal
Metric: cacheforge_health_check_latency_seconds
Threshold: >5s for 30 seconds
Current Value: timeout (no response)
```

## Timeline

**14:27 UTC** - Health check alert triggered for cacheforge-prod-01

**14:31 UTC** - On-call engineer attempts to connect via cacheforge-cli:
```
$ cacheforge-cli -h cacheforge-prod-01 PING
Error: connection timeout after 10s
```

**14:33 UTC** - Second node (cacheforge-prod-02) also stops responding

**14:35 UTC** - Process is running but unresponsive:
```
$ ps aux | grep cacheforge
cacheforge  1234  85.2  4.1 2847292 168048 ?  Sl   10:00  312:45 /usr/bin/cacheforge-server
```

**14:38 UTC** - Thread dump obtained via gdb attach:
```
Thread 4 (LWP 1238):
#0  __lll_lock_wait () at ../sysdeps/unix/sysv/linux/x86_64/lowlevellock.S:152
#1  __GI___pthread_mutex_lock (mutex=0x7f8a1c002100) at pthread_mutex_lock.c:115
#2  cacheforge::HashTable::remove(std::string const&) at storage/hashtable.cpp:52
...

Thread 7 (LWP 1241):
#0  __lll_lock_wait () at ../sysdeps/unix/sysv/linux/x86_64/lowlevellock.S:152
#1  __GI___pthread_mutex_lock (mutex=0x7f8a1c002080) at pthread_mutex_lock.c:115
#2  cacheforge::HashTable::set(std::string const&, cacheforge::Value) at storage/hashtable.cpp:21
...
```

**14:42 UTC** - Production load balancer removes both nodes. Traffic failing over to DR cluster.

**14:50 UTC** - Both nodes restarted. Services restored.

---

## Grafana Dashboard Observations

### Request Patterns Before Hang

```
Time: 14:00-14:27 UTC (before incident)

SET operations/sec:     4,500
GET operations/sec:    12,000
DELETE operations/sec:  3,800
EXPIRE callbacks/sec:   1,200

CPU Usage: 78% (normal)
Memory: 61% (normal)
```

### Connection State

```
Active connections: 847
Connections in CLOSE_WAIT: 0
Connection count trend: stable
```

### Thread State at Hang Time

```
Running threads: 2
Blocked threads: 14
Total threads: 16

Blocking syscall distribution:
  futex(FUTEX_WAIT): 14 threads
```

---

## Reproduction Attempts

QA was able to reproduce the hang by running concurrent SET and DELETE operations:

```bash
# Terminal 1: Rapid SETs
for i in $(seq 1 10000); do
  cacheforge-cli SET key_$i value_$i &
done

# Terminal 2: Rapid DELETEs
for i in $(seq 1 10000); do
  cacheforge-cli DEL key_$i &
done

# Result: Server hangs within 30-60 seconds
```

Sequential operations work fine. The hang only occurs with concurrent SET and DELETE.

---

## Additional Observations

1. **Single-threaded mode**: When running with `--threads=1`, the server never hangs. The issue only manifests with multiple worker threads.

2. **Thread dump analysis**: Two threads appear to be waiting for each other. One thread holds mutex A and waits for mutex B. Another thread holds mutex B and waits for mutex A.

3. **Specific operations**: The deadlock always involves the hashtable operations, specifically SET and DELETE running concurrently.

4. **Similar incident**: A similar hang was reported 2 weeks ago but was attributed to "network issues" and resolved with a restart.

---

## Customer Impact

- 18 minutes of partial outage (50% of traffic affected)
- 847 active connections dropped
- ~120,000 requests failed during the incident
- SLA at risk (99.99% target, currently tracking at 99.95% for the month)

---

## Investigation Questions

1. Why are two threads waiting for each other's locks?
2. What is the lock acquisition pattern in SET vs DELETE operations?
3. Why does single-threaded mode work correctly?
4. Are there other operations with similar locking patterns?

---

## Relevant Logs

Logs show normal operation until the hang:
```
2024-01-18T14:26:58Z INFO  Processed 4523 SET operations in last second
2024-01-18T14:26:59Z INFO  Processed 4498 SET operations in last second
2024-01-18T14:27:00Z INFO  Processed 4511 SET operations in last second
2024-01-18T14:27:01Z <no more log output>
```

---

## Files to Investigate

Based on the stack traces:
- `src/storage/hashtable.cpp` - Lock acquisition patterns
- `src/storage/hashtable.h` - Mutex definitions

---

**Status**: INVESTIGATING
**Assigned**: @cache-platform-team
**Post-mortem**: Scheduled for 2024-01-19 10:00 UTC
