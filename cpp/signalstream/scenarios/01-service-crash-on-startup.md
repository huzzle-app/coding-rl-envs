# Incident Report: Services Crashing on Startup

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-18 02:15 UTC
**Acknowledged**: 2024-01-18 02:18 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: signalstream-gateway-prod-1 CrashLoopBackOff
Host: signalstream-gateway-prod-1.us-east-1.internal
Event: Container terminated with exit code 139 (SIGSEGV)
Restart Count: 5
```

## Timeline

**02:15 UTC** - Initial alert fired for gateway service crash

**02:17 UTC** - Multiple services entering CrashLoopBackOff:
- gateway (5 restarts)
- ingest (4 restarts)
- router (4 restarts)
- monitor (3 restarts)

**02:22 UTC** - All services offline, platform completely down

**02:30 UTC** - Rollback to previous image attempted but same issue persists

**02:45 UTC** - Issue isolated to static initialization during service startup

## Core Dump Analysis

### Gateway Service Stack Trace

```
Program received signal SIGSEGV, Segmentation fault.
0x00007f3a2c4a1234 in std::__cxx11::basic_string<char>::basic_string() from /lib/libstdc++.so.6

Thread 1 (crashed):
#0  0x00007f3a2c4a1234 in std::__cxx11::basic_string<char>::basic_string()
#1  0x0000555555678abc in KafkaConfig::KafkaConfig() at src/config/kafka_config.cpp:23
#2  0x0000555555678def in __static_initialization_and_destruction_0() at src/config/kafka_config.cpp:8
#3  0x00007f3a2c123456 in __libc_start_main
```

### Ingest Service Stack Trace

```
Program received signal SIGSEGV, Segmentation fault.

Thread 1 (crashed):
#0  0x0000555555601abc in ServiceRegistry::getInstance()
#1  0x0000555555602def in IngestService::IngestService() at src/services/ingest.cpp:45
#2  0x0000555555600123 in main() at src/main.cpp:12

Note: getInstance() accessed before singleton was constructed
```

## Kubernetes Events

```yaml
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  3m12s              default-scheduler  Successfully assigned signalstream/gateway-abc123
  Normal   Pulled     3m10s              kubelet            Container image pulled
  Warning  BackOff    2m (x5 over 3m)    kubelet            Back-off restarting failed container

  Last State:
    Terminated:
      Exit Code:    139
      Reason:       Error
      Started:      Thu, 18 Jan 2024 02:15:32 +0000
      Finished:     Thu, 18 Jan 2024 02:15:32 +0000
```

## Observations

### Startup Timing Issues
- Services crash immediately on startup, before processing any requests
- The crash occurs during static initialization, before `main()` is called
- Some services crash reliably, others crash ~70% of the time (order-dependent)

### AddressSanitizer Output (when enabled)

```
=================================================================
==12345==ERROR: AddressSanitizer: SEGV on unknown address 0x000000000000
    #0 0x555555678abc in std::__cxx11::basic_string<char>::basic_string()
    #1 0x555555678def in KafkaConfig::KafkaConfig() /app/src/config/kafka_config.cpp:23
    #2 0x555555679123 in __static_initialization_and_destruction_0

AddressSanitizer can not provide additional info.
SUMMARY: AddressSanitizer: SEGV
```

### Service Registry Access Pattern

```
2024-01-18T02:15:32.001Z TRACE [gateway] Attempting to get ServiceRegistry instance
2024-01-18T02:15:32.001Z ERROR [gateway] FATAL: ServiceRegistry accessed before construction
2024-01-18T02:15:32.001Z TRACE [gateway] Thread accessing registry: 0x7f3a2c000000
2024-01-18T02:15:32.002Z TRACE [gateway] Another thread: 0x7f3a2c100000
```

## Health Check Behavior

Monitor service reports healthy even when other services are crashing:

```json
{
  "status": "healthy",
  "components": {
    "gateway": "unknown",
    "ingest": "unknown",
    "router": "unknown"
  },
  "timestamp": "2024-01-18T02:16:00Z"
}
```

The health check appears to report "healthy" before all initialization is complete.

## Configuration Validation

When attempting to start with invalid database pool settings:

```
2024-01-18T02:20:15Z [config] Loading database pool configuration
2024-01-18T02:20:15Z [config] Pool size: 0
2024-01-18T02:20:15Z [config] Connection timeout: -1ms
2024-01-18T02:20:16Z [ERROR] Database operation failed: no available connections
```

The configuration system appears to accept invalid values (zero pool size, negative timeout).

## CMake Build Warnings

During build, the following warnings were observed:

```
CMake Warning: C++20 features may not be fully supported
...
src/shared/constexpr_utils.hpp:42:1: error: constexpr function never produces a constant expression
    42 | constexpr auto compute_hash(std::string_view sv) {
       | ^~~~~~~~~
src/shared/constexpr_utils.hpp:45:12: note: non-constexpr call in constexpr context
    45 |     return std::hash<std::string_view>{}(sv);
```

## Questions for Investigation

1. Why do services crash before `main()` is even called?
2. What is the "static initialization order fiasco" and how does it apply here?
3. Why is the ServiceRegistry singleton not thread-safe?
4. Why does the database pool accept invalid configuration values?
5. Why does the health check report ready before initialization completes?
6. Why are constexpr functions failing to compile with C++20 features?

## Attempted Mitigations

1. Rolling back to previous version - same crash behavior
2. Increasing startup probe timeout - services crash before probe runs
3. Reducing replica count to 1 - crashes still occur
4. Disabling health checks - no effect on startup crash

---

**Status**: INVESTIGATING
**Assigned**: @platform-team
**Root Cause**: Suspected static initialization order fiasco in shared library code
