# SignalStream - Alternative Tasks

## Overview

These alternative tasks provide different entry points into the SignalStream codebase, each focusing on a specific type of software engineering work within the signal processing and streaming domain. Choose from feature development, refactoring, optimization, API extension, and modernization challenges.

## Environment

- **Language**: C++20
- **Infrastructure**: Kafka, PostgreSQL, Redis, InfluxDB, etcd
- **Difficulty**: Apex-Principal
- **Build System**: CMake with CTest

## Tasks

### Task 1: Feature Development - Sliding Window Aggregation

Extend SignalStream's time-window aggregation system to support sliding (overlapping) windows for computing rolling statistics. Implement a `SlidingWindowAggregator` class that accepts configurable window duration and slide interval parameters, enabling rolling averages and moving standard deviations for financial clients. Handle edge cases including windows with no data, NaN values, and out-of-order timestamps while maintaining low-latency guarantees.

### Task 2: Refactoring - Connection Pool Resource Management

Refactor the storage layer from manual resource management to RAII-based patterns. Create a `ScopedConnection` wrapper that guarantees connection return to the pool regardless of execution path. Apply this pattern consistently across `StorageEngine` and `QueryEngine` to make resource leaks structurally impossible. Also address similar patterns in buffer allocation and prepared statement lifecycle management.

### Task 3: Performance Optimization - Lock-Free Ingest Pipeline

Optimize the `IngestBuffer` class to use lock-free data structures, reducing contention in high-throughput scenarios where multiple producer threads create bottlenecks. Fix the ABA problem in existing `LockFreeNode` structures, apply correct memory ordering for atomic operations, and eliminate false sharing. Target at least 3x throughput improvement with 8 concurrent producers and pass ThreadSanitizer validation.

### Task 4: API Extension - Streaming Query Interface

Add a cursor-based streaming query API to the `QueryEngine` for incremental result retrieval. Implement a `StreamingCursor` class supporting configurable fetch sizes, pause/resume semantics, and lazy evaluation of underlying storage. Handle concurrent access correctly, managing cursor cleanup even when clients abandon iteration early, while supporting timeout/expiration for long-running queries.

### Task 5: Migration - Modern C++ Concepts and Constraints

Migrate template utilities from C++17 SFINAE techniques to C++20 concepts and constraints for improved readability and error messages. Replace `enable_if` with `requires` clauses, fix overly restrictive concepts (like `Streamable`), correct operator precedence in constraint expressions, and refactor perfect forwarding patterns. Add deduction guides and fix ADL issues in serialization code.

## Getting Started

```bash
# Clean build
rm -rf build
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel

# Run all tests
cd build && ctest --output-on-failure
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). Each task includes specific requirements for functionality, thread safety, performance, and API compatibility.
