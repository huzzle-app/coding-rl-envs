# CacheForge - Greenfield Tasks

## Overview

CacheForge greenfield tasks involve implementing three complete new modules from scratch, extending the cache system with production-grade features. Each module includes detailed interface specifications and comprehensive test requirements, following established architectural patterns throughout the codebase.

## Environment

- **Language**: C++20
- **Infrastructure**: CMake 3.20+ with vcpkg, Boost.Asio, spdlog, Google Test, PostgreSQL 15, Redis 7
- **Difficulty**: Senior (4-8h per task)

## Tasks

### Task 1: Cache Warming Service (Greenfield Implementation)

Implement a `CacheWarmer` module that pre-populates the cache with frequently accessed data on startup or on-demand. The service reads warming hints from a configuration source and proactively loads entries before client requests arrive. Key features include priority-ordered processing, progress tracking, graceful shutdown, and configurable batching with delays. Supports both synchronous and asynchronous warming modes with statistics reporting.

**Interface Contract**: Create `src/warming/cache_warmer.h` with `CacheWarmer`, `IWarmingHintSource`, and `FileWarmingHintSource` classes. See [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) for complete interface specification.

**Key Components**:
- `WarmingHint` struct with key, priority, and TTL
- `WarmingLoader` callback for fetching values
- `IWarmingHintSource` abstract interface for hint sources
- `FileWarmingHintSource` for file-based hints
- `CacheWarmer` with batch processing, progress tracking, and thread safety

### Task 2: Compression Pipeline (Greenfield Implementation)

Implement a `CompressionPipeline` module that transparently compresses cache values above a configurable size threshold. The pipeline reduces memory usage for large values while maintaining simple APIs for callers. Supports multiple algorithms (LZ4, Snappy, Zstd), automatic fallback for poor compression ratios, and comprehensive statistics tracking.

**Interface Contract**: Create `src/compression/compression_pipeline.h` with `CompressionPipeline`, `ICompressor`, and `LZ4Compressor` classes. See [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) for complete interface specification.

**Key Components**:
- `CompressionAlgorithm` enum with supported algorithms
- `ICompressor` abstract interface for pluggable algorithms
- `LZ4Compressor` reference implementation
- `CompressedValue` wrapper with serialization
- `CompressionPipeline` with transparent encoding/decoding and statistics

### Task 3: Cache Analytics Collector (Greenfield Implementation)

Implement a `CacheAnalytics` module that collects and exposes cache performance metrics including hit/miss rates, latency distributions, hot key detection, and memory efficiency. The collector enables operators to monitor cache health and optimize configurations. Uses lock-free atomics for low-overhead recording and supports multiple export sinks (JSON, Prometheus).

**Interface Contract**: Create `src/analytics/cache_analytics.h` with `CacheAnalytics`, `IAnalyticsSink`, and `JsonFileSink` classes. See [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) for complete interface specification.

**Key Components**:
- `AnalyticsSnapshot` struct capturing point-in-time metrics
- `OperationRecord` for detailed operation tracking
- `LatencyBucket` for latency histogram
- `IAnalyticsSink` abstract interface for export destinations
- `JsonFileSink` for file-based export
- `CacheAnalytics` with concurrent recording and percentile computation
- `ScopedLatencyTimer` RAII helper for automatic latency measurement

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
ctest -R integration_tests --output-on-failure
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).

Each task includes:
- **15-25+ unit tests** covering all functionality and edge cases
- **Integration tests** demonstrating module interaction with HashTable
- **Thread safety verification** with ThreadSanitizer (`-fsanitize=thread`)
- **Memory safety verification** with AddressSanitizer (`-fsanitize=address`)
- **Performance requirements** (e.g., recording overhead < 500ns for Analytics)
- **Backward compatibility** with existing cache interfaces

All tests must pass with zero warnings from both sanitizers.
