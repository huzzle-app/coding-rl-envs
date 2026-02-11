# SignalStream - Alternative Tasks

These alternative tasks provide different entry points into the SignalStream codebase, each focusing on a specific type of software engineering work within the signal processing and streaming domain.

---

## Task 1: Feature Development - Sliding Window Aggregation

### Description

SignalStream's current time-window aggregation system uses fixed, non-overlapping windows for computing statistics on incoming data streams. Financial clients have requested sliding window support where windows can overlap, enabling them to compute rolling averages, moving standard deviations, and other time-series metrics that update continuously as new data arrives.

The feature requires extending the `Aggregator` class and related time-window handling code to support configurable window sizes and slide intervals. For example, a 5-minute window with a 1-minute slide would produce overlapping aggregations every minute, each covering the most recent 5 minutes of data. This pattern is critical for real-time anomaly detection and trend analysis in high-frequency trading scenarios.

The implementation must maintain SignalStream's low-latency guarantees while handling the increased memory pressure from maintaining multiple overlapping windows. Consider the implications for the existing numerical precision handling, NaN propagation, and floating-point accumulation patterns already present in the aggregation code.

### Acceptance Criteria

- Implement a `SlidingWindowAggregator` class that accepts window duration and slide interval parameters
- Support configurable overlap ratios (e.g., 50% overlap means slide = window_size / 2)
- Compute standard aggregation metrics (sum, mean, min, max, variance, count) for each window emission
- Maintain proper floating-point precision using compensated summation techniques
- Handle edge cases: windows with no data points, NaN values in the stream, timestamps out of order
- Provide an eviction mechanism to remove data points older than the maximum window span
- Ensure thread-safe access when multiple consumers read from the same sliding window aggregator

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 2: Refactoring - Connection Pool Resource Management

### Description

The current storage layer implements connection pooling with manual resource management patterns that have proven error-prone in production. Connection leaks occur when exceptions are thrown before connections are returned to the pool, and the mismatched allocation/deallocation patterns make the code difficult to audit. The codebase needs a comprehensive refactoring to adopt RAII-based resource management throughout.

The refactoring should introduce a `ScopedConnection` wrapper that guarantees connection return to the pool regardless of the execution path (normal return, exception, early exit). This pattern should be applied consistently across the `StorageEngine`, `QueryEngine`, and any other components that acquire pooled resources. The goal is to make resource leaks structurally impossible rather than relying on careful programming.

Beyond connections, the refactoring should address similar patterns in buffer allocation (`allocate_buffer`/`free_buffer`), prepared statement handles, and any other manually-managed resources. Consider using `unique_ptr` with custom deleters, scope guards, or dedicated RAII wrapper classes as appropriate for each resource type.

### Acceptance Criteria

- Create a `ScopedConnection` RAII wrapper that returns connections to the pool in its destructor
- Refactor `StorageEngine::execute_query` to use the scoped connection pattern
- Ensure connections are returned even when exceptions are thrown during query execution
- Replace the `allocate_buffer`/`free_buffer` pattern with a RAII buffer class or `unique_ptr` with custom deleter
- Refactor `QueryEngine::prepare_statement` to use RAII for prepared statement lifecycle management
- Remove all raw resource acquisition patterns that require manual cleanup calls
- Maintain existing functionality and API compatibility where possible

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 3: Performance Optimization - Lock-Free Ingest Pipeline

### Description

SignalStream's data ingestion pathway currently uses mutex-based synchronization in the `IngestBuffer` class, which creates contention under high-throughput scenarios. Profiling has shown that the ingest buffer becomes a bottleneck when multiple producer threads push data simultaneously, with lock contention consuming up to 40% of CPU time during peak load.

The optimization requires redesigning the ingest buffer to use lock-free data structures for the producer side of the pipeline. The implementation should address the ABA problem correctly (the existing `LockFreeNode` structure has this flaw), use appropriate memory ordering for atomic operations, and avoid false sharing between producer threads. The goal is to achieve near-linear throughput scaling as producer thread count increases.

Care must be taken to correctly handle the consumer side, which may still use blocking synchronization while waiting for data. The condition variable usage needs to be integrated properly with the lock-free structure, ensuring no lost wakeups or spurious returns occur.

### Acceptance Criteria

- Implement a lock-free multi-producer queue for the `IngestBuffer::push` operation
- Use generation counters or hazard pointers to prevent the ABA problem
- Apply appropriate memory ordering (acquire/release semantics) for all atomic operations
- Eliminate false sharing by properly aligning and padding atomic variables
- Maintain correct consumer blocking behavior with condition variable integration
- Fix the condition variable predicate loop to handle spurious wakeups correctly
- Achieve at least 3x throughput improvement with 8 concurrent producer threads
- Pass all existing tests under ThreadSanitizer without data race warnings

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 4: API Extension - Streaming Query Interface

### Description

The current `QueryEngine` provides a batch-oriented API where clients submit a query and receive all results at once. For large result sets in time-series queries, this causes memory pressure and high latency-to-first-result. Financial clients need a streaming query interface that returns results incrementally as they are produced, enabling progressive rendering and early termination.

The extension should add a cursor-based streaming API to the `QueryEngine` that allows clients to iterate through results in configurable batch sizes. The interface should support pause/resume semantics, allowing clients to control backpressure. Results should be produced lazily, with the underlying storage iteration only advancing as the client consumes data.

The implementation must handle concurrent access correctly: multiple clients may have open cursors on the same data, and data modifications may occur during iteration. The existing iterator invalidation issues in the storage layer must be considered when designing the streaming interface.

### Acceptance Criteria

- Add a `StreamingCursor` class that provides incremental access to query results
- Implement `QueryEngine::execute_streaming` that returns a cursor instead of a vector
- Support configurable fetch sizes (e.g., 100 results per batch)
- Provide `has_more()`, `fetch_next_batch()`, and `close()` cursor operations
- Handle cursor cleanup correctly even if the client abandons iteration early
- Ensure concurrent modifications to underlying data don't corrupt active cursors
- Maintain proper mutex handling across the cursor lifecycle (no leaks on exceptions)
- Support cursor timeout/expiration for long-running queries

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 5: Migration - Modern C++ Concepts and Constraints

### Description

SignalStream was originally developed with C++17 and later updated to C++20, but many template utilities still use the older SFINAE-based techniques (`enable_if`, `void_t`) rather than C++20 concepts and constraints. The template code is difficult to read, produces poor error messages, and has subtle bugs in the constraint logic. A migration to modern C++20 idioms would improve maintainability and catch errors at compile time with clearer diagnostics.

The migration should convert SFINAE-based type constraints to C++20 concepts throughout the codebase. This includes fixing the overly restrictive `Streamable` concept (which incorrectly requires non-const references), correcting the `requires` clause precedence errors, and ensuring concepts compose correctly. The perfect forwarding patterns should be updated to use proper forwarding references.

Additionally, the migration should address the CTAD (Class Template Argument Deduction) issues by adding appropriate deduction guides, and fix ADL (Argument-Dependent Lookup) problems in the serialization code where qualified calls prevent customization points from working correctly.

### Acceptance Criteria

- Replace all `std::enable_if_t` usage with C++20 `requires` clauses or concept constraints
- Fix the `Streamable` concept to accept both const and non-const member access
- Correct the `requires` clause operator precedence with proper parenthesization
- Update `forward_value` to use proper forwarding reference (`T&&`) with `std::forward`
- Add deduction guides for `DataWrapper` and any other class templates using CTAD
- Refactor `to_json` to use unqualified calls enabling ADL for `serialize` customization
- Ensure all template instantiations produce clear error messages for invalid types
- Verify that the `process_numeric` SFINAE correctly enables for intended types only

### Test Command

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```
