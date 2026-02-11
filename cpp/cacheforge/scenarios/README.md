# CacheForge Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, security audits, and operational issues you might encounter as an engineer on the CacheForge team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, and user reports. Your task is to:

1. Read the scenario to understand the reported symptoms
2. Investigate the codebase to identify root causes
3. Implement fixes for the underlying bugs
4. Verify fixes with the test suite
5. Ensure no regressions are introduced

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-deadlock-under-load.md](./01-deadlock-under-load.md) | PagerDuty Incident | Critical | Server hangs, threads blocked on mutexes |
| [02-memory-corruption-crashes.md](./02-memory-corruption-crashes.md) | Incident Report | Critical | SIGSEGV crashes, heap corruption, double-free |
| [03-security-audit-findings.md](./03-security-audit-findings.md) | Security Audit | High | Buffer overflow, integer overflow, memory exhaustion |
| [04-startup-failures.md](./04-startup-failures.md) | Deployment Blocker | Blocker | Crashes on startup, signal handler issues |
| [05-replication-eviction-anomalies.md](./05-replication-eviction-anomalies.md) | Support Ticket | High | Empty logs, eviction failures, stale data |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Clear deadlock symptoms with stack traces pointing to specific functions
- **Scenario 2**: Multiple crash types requiring memory analysis tools (ASan, Valgrind)
- **Scenario 3**: Security-focused investigation requiring protocol and API analysis
- **Scenario 4**: Subtle C++ initialization and signal handling issues
- **Scenario 5**: Concurrency issues requiring understanding of memory ordering and condition variables

## Bug Categories Covered

| Category | Scenarios |
|----------|-----------|
| Concurrency (A) | 01, 05 |
| Memory Management (B) | 02 |
| Smart Pointers & RAII (C) | 02 |
| Move Semantics & UB (D) | 05 |
| Security (E) | 03 |
| Setup/Configuration (L) | 04 |

## Tips for Investigation

1. **Build with sanitizers**: `cmake -DCMAKE_CXX_FLAGS="-fsanitize=address,thread"`
2. **Check stack traces**: Core dumps often point directly to problematic code
3. **Use Valgrind**: `valgrind --tool=memcheck ./cacheforge-server`
4. **Run tests with race detection**: Build with ThreadSanitizer
5. **Search for patterns**: `grep -rn "lock" src/` to find all locking code
6. **Check memory ordering**: Look for `memory_order_relaxed` in concurrent code

## Running Tests

```bash
# Build the project
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel

# Run all tests
cd build && ctest --output-on-failure

# Run specific test categories
ctest -R concurrency_tests --output-on-failure
ctest -R security_tests --output-on-failure
```

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation with file locations
- Test files in `tests/` directory contain assertions that exercise these bugs
