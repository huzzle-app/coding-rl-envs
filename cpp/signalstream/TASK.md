# SignalStream - Real-Time Data Processing Platform

## Task Description

You are debugging a real-time data processing platform for financial and IoT streams, built with C++20 and organized as 10 microservices. The platform handles data ingestion, routing, transformation, aggregation, storage, querying, and alerting with low-latency requirements.

## Known Issues

The codebase needs attention. Failures span configuration, service logic, and integration points.

The codebase contains issues across 10 microservices and a shared library that need to be identified and fixed. All 510+ tests must pass before the task is complete.

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Run all tests in Docker
docker compose -f docker-compose.test.yml up --build

# Or build locally and run tests
cmake -B build \
 -DCMAKE_TOOLCHAIN_FILE=${VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake \
 -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel $(nproc)
cd build && ctest --output-on-failure
```

## Architecture

SignalStream is a microservices platform with 10 C++20 services:

| Service | Port | Purpose |
| Gateway | 8000 | WebSocket/REST API entry point |
| Auth | 8001 | JWT authentication, API keys |
| Ingest | 8002 | Data ingestion from streams |
| Router | 8003 | Message routing to consumers |
| Transform | 8004 | Data transformation pipelines |
| Aggregate | 8005 | Time-series aggregation |
| Storage | 8006 | Persistence layer |
| Query | 8007 | Query engine |
| Alert | 8008 | Alerting rules engine |
| Monitor | 8009 | Metrics and health checks |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| Kafka 7.5 | Message queue, event streaming |
| PostgreSQL 15 | Persistent storage |
| Redis 7 | Caching, rate limiting |
| InfluxDB 2 | Time-series metrics |
| etcd 3.5 | Service discovery, distributed locks |

## Test Categories

| Category | Tests | Focus |
| Unit | ~180 | Individual functions, edge cases |
| Integration | ~120 | Service interactions, message flow |
| Concurrency | ~60 | Race conditions, deadlocks, atomics |
| Security | ~50 | Authentication, injection, overflow |
| Performance | ~50 | Latency, throughput |
| Chaos | ~30 | Failure scenarios, partition tolerance |
| System | ~20 | End-to-end data pipeline workflows |

## Success Criteria

- All 510+ tests pass
- No compiler warnings
- No undefined behavior (AddressSanitizer, ThreadSanitizer, UBSanitizer clean)
- No memory leaks (Valgrind/ASan clean)
- No data races
- Financial/numerical calculations use proper precision

## C++ Patterns to Watch

```cpp
// ABA problem in lock-free queue (BUG)
if (head.compare_exchange_weak(old_head, new_head)) // Without generation counter!

// False sharing (BUG)
struct alignas(64) Counter { std::atomic<int> value; }; // Need padding

// string_view dangling (BUG)
std::string_view sv = get_temporary_string(); // Backing string destroyed!

// shared_ptr cycle (BUG)
struct A { std::shared_ptr<B> b; };
struct B { std::shared_ptr<A> a; }; // Use weak_ptr!

// Signed overflow UB (BUG)
int64_t delta = timestamp2 - timestamp1; // UB if result overflows!

// SFINAE wrong condition (BUG)
template<typename T, std::enable_if_t<std::is_integral_v<T>>* = nullptr>
void process(T val); // Should check is_floating_point for float overload
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter. Each scenario describes **symptoms only** - use them to practice investigation and root cause analysis.

| Scenario | Type | Focus Areas |
| [01-service-crash-on-startup.md](./scenarios/01-service-crash-on-startup.md) | PagerDuty Incident | Static initialization, configuration validation |
| [02-data-corruption-under-load.md](./scenarios/02-data-corruption-under-load.md) | Customer Escalation | Concurrency, memory safety, race conditions |
| [03-security-audit-findings.md](./scenarios/03-security-audit-findings.md) | Security Report | JWT bypass, injection, buffer overflow |
| [04-alerting-system-failures.md](./scenarios/04-alerting-system-failures.md) | Slack Thread | Distributed state, circuit breakers, retries |
| [05-aggregation-precision-loss.md](./scenarios/05-aggregation-precision-loss.md) | Support Ticket | Numerical precision, floating-point, NaN handling |

## Hints

1. **Start with L category** -- setup bugs block services from starting. L1 (static init order fiasco) must be fixed first.
2. Use AddressSanitizer (`-fsanitize=address`) to catch memory bugs.
3. Use ThreadSanitizer (`-fsanitize=thread`) to catch data races.
4. Use UBSanitizer (`-fsanitize=undefined`) to catch undefined behavior.
5. Template bugs (K category) are subtle -- look for SFINAE conditions, ADL lookup, and constexpr violations.
6. Numerical bugs need epsilon comparisons and overflow checks.
7. Smart pointer cycles are in gateway/websocket code -- break with `weak_ptr`.
8. The dependency chain means some bugs are not fixable until prerequisites are resolved.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Sliding Window Aggregation, Connection Pool RAII, Lock-Free Ingest, Streaming Queries, Modern C++ Concepts |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | FFT Processing Pipeline, Signal Correlation Engine, Alert Rule Evaluator |

These tasks test different software engineering skills while using the same codebase.
