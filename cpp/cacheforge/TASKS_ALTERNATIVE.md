# CacheForge - Alternative Task Specifications

This document describes alternative development tasks for the CacheForge high-performance caching platform. Each task represents a realistic engineering challenge that would be encountered when extending or maintaining a production cache server.

---

## Task 1: LFU Eviction Policy Implementation (Feature Development)

### Description

CacheForge currently supports only LRU (Least Recently Used) eviction through the `EvictionManager` class. Many production workloads benefit from LFU (Least Frequently Used) eviction, which keeps frequently-accessed items in cache even if they were not accessed recently. This is particularly valuable for scenarios with time-based access patterns (e.g., hourly batch jobs that access certain keys intensively).

Implement a new LFU eviction policy that tracks access frequency for each cache entry. The implementation should use an O(1) algorithm for both access recording and victim selection, similar to the approach described in the "LFU Cache" problem. The policy should support frequency decay over time to prevent "cache pollution" from keys that were heavily accessed in the past but are no longer relevant.

The eviction manager should be configurable at startup to use either LRU or LFU policy, with the ability to specify decay parameters for the LFU implementation.

### Acceptance Criteria

- New `LFUEvictionManager` class implementing the same interface as `EvictionManager`
- O(1) time complexity for `record_access()`, `record_insert()`, and `evict_one()` operations
- Configurable frequency decay mechanism (e.g., halving frequencies every N minutes)
- Factory function or configuration option to select between LRU and LFU at runtime
- Minimum frequency buckets implemented using linked lists for efficient victim selection
- Thread-safe implementation with proper mutex protection
- Unit tests covering frequency tracking, decay behavior, and eviction ordering
- Integration tests verifying correct behavior under concurrent access

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 2: Memory Pool Slab Allocator Refactoring (Refactoring)

### Description

The current `MemoryPool` implementation uses a contiguous vector for storage, which causes pointer invalidation when the pool grows. This design flaw leads to dangling pointers and memory corruption in long-running cache instances. The pool also lacks proper copy/move semantics, risking double-free vulnerabilities.

Refactor the memory pool to use a slab allocator design where memory is organized into fixed-size slabs. Each slab should be independently allocated and never moved once created. This ensures that pointers returned by `allocate()` remain valid for the lifetime of the pool. The slab allocator should also implement proper RAII semantics with deleted copy operations and explicit move semantics.

Consider implementing a thread-local slab cache to reduce mutex contention in high-concurrency scenarios. The refactored design should maintain backward compatibility with the existing `MemoryPool` interface while providing stronger memory safety guarantees.

### Acceptance Criteria

- Slab-based allocation where each slab is a fixed-size memory block
- Pointers remain valid even when new slabs are allocated (no vector reallocation)
- Deleted copy constructor and copy assignment operator
- Implemented move constructor and move assignment operator
- Optional thread-local slab caching for reduced lock contention
- Memory usage statistics (total allocated, free blocks per slab, fragmentation ratio)
- Backward compatible with existing `TypedPool` template wrapper
- Unit tests for pointer stability, move semantics, and thread safety

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 3: Lock-Free Hash Table for Read-Heavy Workloads (Performance Optimization)

### Description

The current `HashTable` implementation uses a shared mutex for read/write locking, which creates contention under high-concurrency read-heavy workloads. Production cache servers typically experience read-to-write ratios of 100:1 or higher, making lock-free reads a significant performance opportunity.

Implement a lock-free hash table optimized for read-heavy workloads using hazard pointers or epoch-based reclamation for safe memory management. The implementation should allow concurrent reads without any locking while serializing writes. Consider using atomic operations for bucket access and implementing a resize strategy that does not block readers.

The lock-free implementation should be available as an alternative storage backend, configurable at startup based on the expected workload characteristics. Benchmark the implementation against the existing mutex-based approach to validate the performance improvement.

### Acceptance Criteria

- Lock-free read path using atomic load operations
- Safe memory reclamation using hazard pointers or epoch-based reclamation
- Write operations properly serialized to maintain consistency
- Incremental resizing that does not block concurrent readers
- Memory ordering correctly specified for all atomic operations
- No data races when verified with ThreadSanitizer
- Benchmark comparing lock-free vs mutex-based implementation
- Stress tests with high read-to-write ratios (100:1, 1000:1)

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 4: TTL Precision and Lazy Expiration API (API Extension)

### Description

The current `ExpiryManager` provides basic TTL functionality but lacks precision controls and lazy expiration options that production systems require. Some use cases need millisecond-precision TTLs (e.g., rate limiting), while others prefer lazy expiration where expired keys are only removed on access (reducing background thread overhead).

Extend the expiry API to support multiple precision levels (seconds, milliseconds, microseconds) and configurable expiration strategies. Implement lazy expiration as an alternative to the active expiration thread, where expired keys are detected and removed only when accessed. Add support for TTL refresh operations (TOUCH command) and conditional expiration (expire only if TTL would be extended).

The API should also expose expiration statistics: keys expired actively vs lazily, average TTL at expiration, and expiration latency distribution.

### Acceptance Criteria

- Support for millisecond and microsecond precision TTLs
- Lazy expiration mode where keys are removed on access if expired
- Hybrid mode combining lazy expiration with periodic active cleanup
- TTL refresh operation (`touch()`) that updates expiration without resetting value
- Conditional TTL update (`expire_gt()`) that only sets TTL if it extends lifetime
- Expiration statistics: active count, lazy count, average TTL, latency histogram
- Backward compatible with existing `set_expiry()` and `get_ttl()` methods
- Unit tests for precision, lazy expiration, and conditional updates

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 5: Binary Protocol Migration with Backward Compatibility (Migration)

### Description

The current text-based RESP-like protocol has parsing overhead and is vulnerable to injection attacks when user data is not properly escaped. Production deployments are requesting a binary protocol for improved performance and security. The migration must maintain backward compatibility with existing text-mode clients.

Design and implement a binary protocol that encodes commands and responses in a compact, unambiguous format. The protocol should use length-prefixed fields to eliminate parsing ambiguity and prevent buffer overflow vulnerabilities. Implement protocol version negotiation so clients can indicate their preferred protocol, with automatic fallback to text mode for legacy clients.

The parser should be refactored to support both protocols through a common `Command` abstraction, with protocol detection happening transparently on the first received message. Include proper bounds checking and input validation to prevent security vulnerabilities that existed in the text parser.

### Acceptance Criteria

- Binary protocol specification with versioning and magic number header
- Length-prefixed encoding for all variable-length fields
- Protocol auto-detection based on first message byte
- Version negotiation handshake for explicit protocol selection
- Backward compatible with existing text-mode clients
- Bounds checking on all length fields to prevent buffer overflows
- Fuzz testing of binary parser with malformed inputs
- Migration guide documenting protocol differences and upgrade path

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```
