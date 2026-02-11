# SignalStream - Real-Time Data Processing Platform

A high-performance real-time data processing platform for financial and IoT data streams, built with C++20 and modern distributed systems architecture.

## Overview

SignalStream is a distributed system consisting of 10 microservices that handle real-time data ingestion, routing, transformation, aggregation, storage, and alerting for high-frequency financial market data and IoT sensor streams.

 across 11 categories
 (98 CTest + 12678 parametric scenarios)

## Services

| Service | Port | Purpose |
|---------|------|---------|
| Gateway | 8080 | API gateway, load balancing, rate limiting |
| Auth | 8081 | Authentication, authorization, JWT validation |
| Ingest | 8082 | Data ingestion from Kafka, validation, deduplication |
| Router | 8083 | Stream routing based on rules, topic mapping |
| Transform | 8084 | Real-time data transformation, filtering, enrichment |
| Aggregate | 8085 | Windowed aggregations, statistical computations |
| Storage | 8086 | Time-series storage to InfluxDB, archival |
| Query | 8087 | Query API for historical data retrieval |
| Alert | 8088 | Rule-based alerting, threshold monitoring |
| Monitor | 8089 | Service health checks, metrics collection |

## Infrastructure

- **Kafka 3.6**: Event streaming backbone
- **PostgreSQL 15**: Service metadata, configuration
- **Redis 7**: Caching, session storage, distributed locks
- **InfluxDB 2**: Time-series data storage
- **etcd 3.5**: Service discovery, distributed configuration

## Known Issues

Current state: most tests broken. Areas of concern include API endpoints, background processing, and database operations.

## Getting Started

### Build the Project

```bash
# Clean build
rm -rf build
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
```

### Run Tests

```bash
# Run all tests
cd build && ctest --output-on-failure

# Run specific service tests
cd build && ctest -R gateway --output-on-failure
cd build && ctest -R auth --output-on-failure
cd build && ctest -R ingest --output-on-failure
```

### Start Infrastructure

```bash
docker compose up -d
```

## Success Criteria

 to achieve:
- ✅ All tests passing
- ✅ No memory leaks (verified with AddressSanitizer)
- ✅ No data races (verified with ThreadSanitizer)
- ✅ No undefined behavior
- ✅ All services start successfully
- ✅ End-to-end data flow operational

## Reward Thresholds (10-threshold Apex)

| Pass Rate | Reward |
|-----------|--------|
| 100% | 1.0 |
| ≥99% | 0.85 |
| ≥96% | 0.66 |
| ≥90% | 0.47 |
| ≥80% | 0.31 |
| ≥67% | 0.19 |
| ≥52% | 0.11 |
| ≥36% | 0.05 |
| ≥22% | 0.015 |
| <22% | 0.0 |

## Common Pitfalls

- **Static initialization order**: Services crash on startup due to static init fiasco
- **Memory ordering**: Race conditions in lock-free data structures
- **Lifetime management**: string_view dangling references, iterator invalidation
- **Event ordering**: Out-of-order event processing in distributed system
- **Numerical precision**: Float comparison bugs in financial calculations
- **Resource leaks**: Connection pool exhaustion, subscription leaks
- **Template bugs**: SFINAE, ADL, and forwarding reference issues

## Tips

1. Start with Setup/Config bugs - services must start before tests can run
2. Use sanitizers: `-DCMAKE_CXX_FLAGS="-fsanitize=address,undefined"`
3. Enable race detection: `-DCMAKE_CXX_FLAGS="-fsanitize=thread"`
4. Check test output carefully - CTest shows detailed failure info
5. Bug dependencies exist - some bugs must be fixed before others
6. Focus on one service at a time to avoid overwhelming complexity

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Sliding Window Aggregation, Connection Pool RAII, Lock-Free Ingest, Streaming Queries, Modern C++ Concepts |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | FFT Processing Pipeline, Signal Correlation Engine, Alert Rule Evaluator |

These tasks test different software engineering skills while using the same codebase.
