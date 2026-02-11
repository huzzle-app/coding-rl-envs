# CacheForge - Alternative Tasks

## Overview

CacheForge is a high-performance C++20 in-memory cache server that supports alternative development tasks beyond debugging. These five challenges test feature development, refactoring, and optimization skills using a realistic codebase with evolving requirements.

## Environment

- **Language**: C++20
- **Infrastructure**: CMake 3.20+ with vcpkg, Boost.Asio, spdlog, Google Test, PostgreSQL 15, Redis 7
- **Difficulty**: Senior (4-8h per task)

## Tasks

### Task 1: LFU Eviction Policy Implementation (Feature Development)

Extend the cache eviction system beyond the current LRU implementation to support Least Frequently Used (LFU) eviction. This feature benefits production workloads with time-based access patterns where frequently accessed items should remain cached even if not recently accessed. Implement O(1) eviction operations, frequency decay to prevent cache pollution, and configurable runtime selection between LRU and LFU policies.

### Task 2: Memory Pool Slab Allocator Refactoring (Refactoring)

Refactor the current memory pool implementation from a contiguous vector design (prone to pointer invalidation) to a slab allocator architecture. Each slab should be independently allocated and immovable, ensuring pointer stability throughout the pool lifetime. Add proper RAII semantics with deleted copy operations and explicit move support. Consider thread-local slab caching for reduced contention, while maintaining backward compatibility with the existing interface.

### Task 3: Lock-Free Hash Table for Read-Heavy Workloads (Performance Optimization)

Optimize the hash table implementation for production read-heavy workloads (typical 100:1 read-to-write ratios) using lock-free techniques. Replace the current shared mutex with atomic operations for reads while maintaining safe memory reclamation through hazard pointers or epoch-based reclamation. Implement non-blocking resizing that permits concurrent readers, with correctness verified by ThreadSanitizer and benchmarked performance improvement data.

### Task 4: TTL Precision and Lazy Expiration API (API Extension)

Enhance the expiration system to support multiple precision levels (seconds, milliseconds, microseconds) and configurable expiration strategies. Implement lazy expiration where expired keys are removed only on access (reducing background overhead), hybrid active/lazy modes, TTL refresh operations, and conditional expiration updates. Expose expiration statistics including active vs lazy removal counts and latency distributions.

### Task 5: Binary Protocol Migration with Backward Compatibility (Migration)

Migrate from the text-based RESP-like protocol to a binary protocol that reduces parsing overhead and eliminates injection vulnerabilities. Design length-prefixed encoding for all variable-length fields with automatic protocol detection and version negotiation. Maintain full backward compatibility with text-mode clients through transparent fallback, include proper bounds checking throughout, and provide comprehensive fuzz testing coverage of the binary parser.

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Build project
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel

# Run tests
cd build && ctest --output-on-failure

# Run specific test categories
ctest -R unit_tests --output-on-failure
ctest -R concurrency_tests --output-on-failure
ctest -R security_tests --output-on-failure
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).

Each task includes detailed acceptance criteria covering:
- Functional requirements (interface compliance, performance characteristics)
- Quality requirements (thread safety, memory safety, no data races)
- Testing requirements (unit tests, integration tests, benchmarks)
- Documentation requirements (API documentation, migration guides)

All tests must pass with no ThreadSanitizer or AddressSanitizer warnings.
