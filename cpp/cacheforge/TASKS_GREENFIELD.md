# CacheForge Greenfield Tasks

This document describes new module implementations to extend CacheForge's capabilities. Each task requires building a complete feature from scratch, following existing architectural patterns.

**Test Command:**
```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Task 1: Cache Warming Service

### Overview

Implement a `CacheWarmer` module that pre-populates the cache with frequently accessed data on startup or on-demand. This service reads warming hints from a configuration source (file or callback) and proactively loads entries before client requests arrive.

### Interface Contract

Create `src/warming/cache_warmer.h`:

```cpp
#pragma once
#ifndef CACHEFORGE_CACHE_WARMER_H
#define CACHEFORGE_CACHE_WARMER_H

#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <chrono>
#include <atomic>
#include <thread>
#include <mutex>

namespace cacheforge {

// Hint describing a key to warm
struct WarmingHint {
    std::string key;
    int priority;  // higher = more important
    std::chrono::seconds ttl{0};  // 0 = use default
};

// Loader function type: given a key, returns the value to cache
using WarmingLoader = std::function<std::optional<std::string>(const std::string& key)>;

// Callback type: notified when a key is warmed or fails
using WarmingCallback = std::function<void(const std::string& key, bool success)>;

// Abstract interface for warming hint sources
class IWarmingHintSource {
public:
    virtual ~IWarmingHintSource() = default;
    virtual std::vector<WarmingHint> get_hints() = 0;
    virtual void mark_completed(const std::string& key) = 0;
};

// File-based hint source implementation
class FileWarmingHintSource : public IWarmingHintSource {
public:
    explicit FileWarmingHintSource(const std::string& hints_file_path);
    std::vector<WarmingHint> get_hints() override;
    void mark_completed(const std::string& key) override;

private:
    std::string file_path_;
    std::mutex mutex_;
    std::vector<std::string> completed_keys_;
};

// Cache warming service
class CacheWarmer {
public:
    explicit CacheWarmer(std::shared_ptr<IWarmingHintSource> hint_source);
    ~CacheWarmer();

    // Set the loader function that fetches values for keys
    void set_loader(WarmingLoader loader);

    // Set callback for warming completion events
    void set_callback(WarmingCallback callback);

    // Configure warming behavior
    void set_batch_size(size_t batch_size);
    void set_delay_between_batches(std::chrono::milliseconds delay);
    void set_max_concurrent(size_t max_concurrent);

    // Start warming in background thread
    void start_async();

    // Stop warming (waits for current batch to complete)
    void stop();

    // Warm synchronously (blocks until complete)
    void warm_sync();

    // Warm a single key immediately
    bool warm_key(const std::string& key);

    // Statistics
    size_t keys_warmed() const;
    size_t keys_failed() const;
    size_t keys_pending() const;
    bool is_running() const;

    // Get warming progress (0.0 to 1.0)
    double progress() const;

private:
    std::shared_ptr<IWarmingHintSource> hint_source_;
    WarmingLoader loader_;
    WarmingCallback callback_;

    size_t batch_size_ = 100;
    std::chrono::milliseconds batch_delay_{10};
    size_t max_concurrent_ = 4;

    std::atomic<size_t> keys_warmed_{0};
    std::atomic<size_t> keys_failed_{0};
    std::atomic<size_t> total_keys_{0};
    std::atomic<bool> running_{false};

    std::thread worker_thread_;
    mutable std::mutex mutex_;

    void run_warming_loop();
    void process_batch(const std::vector<WarmingHint>& batch);
};

}  // namespace cacheforge

#endif  // CACHEFORGE_CACHE_WARMER_H
```

### Required Files

| File | Description |
|------|-------------|
| `src/warming/cache_warmer.h` | Interface definitions (above) |
| `src/warming/cache_warmer.cpp` | Implementation |
| `tests/unit/test_cache_warmer.cpp` | Unit tests (15+ test cases) |
| `tests/integration/test_warming_integration.cpp` | Integration with HashTable |

### Implementation Requirements

1. **Thread Safety**: All public methods must be thread-safe. Use mutex protection similar to `EvictionManager`.

2. **Priority Ordering**: Process hints in priority order (highest first). Use `std::priority_queue` or sort before processing.

3. **Graceful Shutdown**: `stop()` must complete the current batch before returning. Use `std::atomic<bool>` for the running flag (see `server.h` pattern).

4. **Progress Tracking**: Maintain atomic counters for warmed/failed/pending keys.

5. **Error Handling**: Failed loads should not abort the warming process. Log errors and continue.

6. **Integration**: The warmer should work with `HashTable::set()` to populate the cache.

### Acceptance Criteria

- [ ] All 15+ unit tests pass
- [ ] Thread safety verified with ThreadSanitizer (`-fsanitize=thread`)
- [ ] No memory leaks under AddressSanitizer (`-fsanitize=address`)
- [ ] Integration test demonstrates warming a HashTable with 1000+ keys
- [ ] Progress reporting is accurate within 1%
- [ ] Graceful shutdown completes within 5 seconds

### Test Cases to Implement

```cpp
// tests/unit/test_cache_warmer.cpp
TEST(CacheWarmerTest, test_warm_single_key);
TEST(CacheWarmerTest, test_warm_multiple_keys_priority_order);
TEST(CacheWarmerTest, test_progress_tracking);
TEST(CacheWarmerTest, test_failed_load_continues);
TEST(CacheWarmerTest, test_stop_completes_current_batch);
TEST(CacheWarmerTest, test_concurrent_warming);
TEST(CacheWarmerTest, test_empty_hint_source);
TEST(CacheWarmerTest, test_callback_invoked);
TEST(CacheWarmerTest, test_batch_size_respected);
TEST(CacheWarmerTest, test_delay_between_batches);
TEST(CacheWarmerTest, test_file_hint_source_parsing);
TEST(CacheWarmerTest, test_mark_completed_persistence);
TEST(CacheWarmerTest, test_duplicate_hints_handled);
TEST(CacheWarmerTest, test_statistics_accuracy);
TEST(CacheWarmerTest, test_restart_after_stop);
```

---

## Task 2: Compression Pipeline

### Overview

Implement a `CompressionPipeline` that transparently compresses cache values above a size threshold. This reduces memory usage for large values while maintaining a simple API for callers.

### Interface Contract

Create `src/compression/compression_pipeline.h`:

```cpp
#pragma once
#ifndef CACHEFORGE_COMPRESSION_PIPELINE_H
#define CACHEFORGE_COMPRESSION_PIPELINE_H

#include <string>
#include <vector>
#include <memory>
#include <optional>
#include <cstdint>
#include <atomic>
#include <mutex>

namespace cacheforge {

// Compression algorithm identifier
enum class CompressionAlgorithm {
    None = 0,
    LZ4 = 1,
    Snappy = 2,
    Zstd = 3
};

// Compression statistics
struct CompressionStats {
    size_t total_compressed = 0;
    size_t total_decompressed = 0;
    size_t bytes_saved = 0;
    size_t compression_failures = 0;
    double average_ratio = 0.0;  // compressed_size / original_size
};

// Abstract compressor interface
class ICompressor {
public:
    virtual ~ICompressor() = default;
    virtual CompressionAlgorithm algorithm() const = 0;
    virtual std::optional<std::vector<uint8_t>> compress(const uint8_t* data, size_t size) = 0;
    virtual std::optional<std::vector<uint8_t>> decompress(const uint8_t* data, size_t size) = 0;
    virtual size_t max_compressed_size(size_t input_size) const = 0;
};

// LZ4 compressor implementation
class LZ4Compressor : public ICompressor {
public:
    CompressionAlgorithm algorithm() const override;
    std::optional<std::vector<uint8_t>> compress(const uint8_t* data, size_t size) override;
    std::optional<std::vector<uint8_t>> decompress(const uint8_t* data, size_t size) override;
    size_t max_compressed_size(size_t input_size) const override;
};

// Compressed value wrapper with metadata header
struct CompressedValue {
    static constexpr uint32_t MAGIC = 0xCF4D5A00;  // "CF" + "MZ" + version

    CompressionAlgorithm algorithm;
    uint32_t original_size;
    std::vector<uint8_t> compressed_data;

    // Serialize to bytes (for storage)
    std::vector<uint8_t> serialize() const;

    // Deserialize from bytes
    static std::optional<CompressedValue> deserialize(const uint8_t* data, size_t size);

    // Check if data is a compressed value (has magic header)
    static bool is_compressed(const uint8_t* data, size_t size);
};

// Compression pipeline configuration
struct CompressionConfig {
    CompressionAlgorithm algorithm = CompressionAlgorithm::LZ4;
    size_t min_size_threshold = 1024;  // Only compress values >= this size
    double min_ratio_threshold = 0.9;   // Only store compressed if ratio < this
    bool enabled = true;
};

// Main compression pipeline
class CompressionPipeline {
public:
    explicit CompressionPipeline(const CompressionConfig& config = {});
    ~CompressionPipeline();

    // Process value for storage (compress if beneficial)
    std::vector<uint8_t> process_for_storage(const uint8_t* data, size_t size);
    std::vector<uint8_t> process_for_storage(const std::string& data);

    // Process value for retrieval (decompress if needed)
    std::vector<uint8_t> process_for_retrieval(const uint8_t* data, size_t size);
    std::string process_for_retrieval_string(const uint8_t* data, size_t size);

    // Configuration
    void set_config(const CompressionConfig& config);
    CompressionConfig get_config() const;
    void enable();
    void disable();
    bool is_enabled() const;

    // Statistics
    CompressionStats get_stats() const;
    void reset_stats();

    // Register custom compressor
    void register_compressor(std::unique_ptr<ICompressor> compressor);

private:
    CompressionConfig config_;
    std::vector<std::unique_ptr<ICompressor>> compressors_;
    mutable std::mutex mutex_;

    // Statistics (atomic for lock-free reads)
    std::atomic<size_t> total_compressed_{0};
    std::atomic<size_t> total_decompressed_{0};
    std::atomic<size_t> bytes_saved_{0};
    std::atomic<size_t> compression_failures_{0};
    std::atomic<uint64_t> ratio_sum_{0};  // Fixed-point for average

    ICompressor* get_compressor(CompressionAlgorithm algo);
    void update_stats(size_t original_size, size_t compressed_size);
};

}  // namespace cacheforge

#endif  // CACHEFORGE_COMPRESSION_PIPELINE_H
```

### Required Files

| File | Description |
|------|-------------|
| `src/compression/compression_pipeline.h` | Interface definitions (above) |
| `src/compression/compression_pipeline.cpp` | Main pipeline implementation |
| `src/compression/lz4_compressor.cpp` | LZ4 implementation (use simple RLE if LZ4 unavailable) |
| `tests/unit/test_compression.cpp` | Unit tests (20+ test cases) |
| `tests/integration/test_compression_integration.cpp` | Integration with Value class |

### Implementation Requirements

1. **Transparent Processing**: Callers should not need to know if data is compressed. The pipeline handles detection automatically via the magic header.

2. **Thread Safety**: All public methods must be thread-safe. Statistics use atomics for lock-free access.

3. **Fallback Behavior**: If compression fails or ratio exceeds threshold, store uncompressed data.

4. **Extensibility**: New compressors can be registered via `register_compressor()`.

5. **Zero-Copy Where Possible**: Avoid unnecessary copies. Accept `const uint8_t*` for input data.

6. **Header Format**: Use a fixed-size header (magic + algorithm + original_size) for compressed values.

### Acceptance Criteria

- [ ] All 20+ unit tests pass
- [ ] Round-trip test: compress then decompress returns original data
- [ ] Values below threshold are not compressed
- [ ] Values with poor compression ratio are stored uncompressed
- [ ] Statistics accurately track compression operations
- [ ] Thread safety verified with ThreadSanitizer
- [ ] Integration test with HashTable storing compressed values

### Test Cases to Implement

```cpp
// tests/unit/test_compression.cpp
TEST(CompressionTest, test_lz4_round_trip);
TEST(CompressionTest, test_compression_below_threshold_skipped);
TEST(CompressionTest, test_poor_ratio_stored_uncompressed);
TEST(CompressionTest, test_compressed_value_serialization);
TEST(CompressionTest, test_is_compressed_detection);
TEST(CompressionTest, test_stats_tracking);
TEST(CompressionTest, test_disable_enable);
TEST(CompressionTest, test_config_update);
TEST(CompressionTest, test_empty_data);
TEST(CompressionTest, test_large_data_compression);
TEST(CompressionTest, test_binary_data_preservation);
TEST(CompressionTest, test_corrupted_header_handling);
TEST(CompressionTest, test_truncated_data_handling);
TEST(CompressionTest, test_custom_compressor_registration);
TEST(CompressionTest, test_concurrent_compress_decompress);
TEST(CompressionTest, test_stats_reset);
TEST(CompressionTest, test_max_compressed_size_estimate);
TEST(CompressionTest, test_multiple_algorithms);
TEST(CompressionTest, test_process_string_convenience);
TEST(CompressionTest, test_decompression_failure_handling);
```

---

## Task 3: Cache Analytics Collector

### Overview

Implement a `CacheAnalytics` module that collects and exposes cache performance metrics: hit/miss rates, latency distributions, hot key detection, and memory efficiency. This enables operators to monitor cache health and optimize configurations.

### Interface Contract

Create `src/analytics/cache_analytics.h`:

```cpp
#pragma once
#ifndef CACHEFORGE_CACHE_ANALYTICS_H
#define CACHEFORGE_CACHE_ANALYTICS_H

#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <chrono>
#include <atomic>
#include <mutex>
#include <functional>

namespace cacheforge {

// Operation types for tracking
enum class CacheOperation {
    Get,
    Set,
    Delete,
    Expire,
    Evict
};

// Single operation record
struct OperationRecord {
    CacheOperation operation;
    std::string key;
    std::chrono::steady_clock::time_point timestamp;
    std::chrono::nanoseconds latency;
    bool hit;  // For Get operations
    size_t value_size;  // For Set operations
};

// Latency histogram bucket
struct LatencyBucket {
    std::chrono::nanoseconds lower_bound;
    std::chrono::nanoseconds upper_bound;
    std::atomic<uint64_t> count{0};
};

// Hot key entry
struct HotKeyEntry {
    std::string key;
    uint64_t access_count;
    double access_rate;  // accesses per second
};

// Memory efficiency metrics
struct MemoryMetrics {
    size_t total_allocated;
    size_t total_used;
    size_t fragmentation_bytes;
    double utilization;  // used / allocated
    size_t average_value_size;
    size_t largest_value_size;
};

// Summary statistics snapshot
struct AnalyticsSnapshot {
    // Time range
    std::chrono::steady_clock::time_point start_time;
    std::chrono::steady_clock::time_point end_time;

    // Operation counts
    uint64_t total_gets;
    uint64_t total_sets;
    uint64_t total_deletes;
    uint64_t total_evictions;
    uint64_t total_expirations;

    // Hit/miss
    uint64_t cache_hits;
    uint64_t cache_misses;
    double hit_rate;  // hits / (hits + misses)

    // Latency (nanoseconds)
    uint64_t avg_get_latency_ns;
    uint64_t p50_get_latency_ns;
    uint64_t p95_get_latency_ns;
    uint64_t p99_get_latency_ns;

    // Hot keys
    std::vector<HotKeyEntry> top_hot_keys;

    // Memory
    MemoryMetrics memory;
};

// Analytics collector configuration
struct AnalyticsConfig {
    bool enabled = true;
    size_t hot_key_tracking_limit = 1000;  // Track top N keys
    size_t latency_bucket_count = 20;
    std::chrono::seconds sampling_window{60};  // Rolling window
    bool track_key_patterns = false;  // Regex pattern grouping
};

// Abstract sink for exporting analytics
class IAnalyticsSink {
public:
    virtual ~IAnalyticsSink() = default;
    virtual void export_snapshot(const AnalyticsSnapshot& snapshot) = 0;
    virtual void flush() = 0;
};

// JSON file sink implementation
class JsonFileSink : public IAnalyticsSink {
public:
    explicit JsonFileSink(const std::string& output_path);
    void export_snapshot(const AnalyticsSnapshot& snapshot) override;
    void flush() override;

private:
    std::string output_path_;
    mutable std::mutex mutex_;
};

// Prometheus metrics sink (stub for extension)
class PrometheusSink : public IAnalyticsSink {
public:
    explicit PrometheusSink(uint16_t port);
    void export_snapshot(const AnalyticsSnapshot& snapshot) override;
    void flush() override;

private:
    uint16_t port_;
};

// Main analytics collector
class CacheAnalytics {
public:
    explicit CacheAnalytics(const AnalyticsConfig& config = {});
    ~CacheAnalytics();

    // Record operations (called from HashTable/EvictionManager)
    void record_get(const std::string& key, bool hit, std::chrono::nanoseconds latency);
    void record_set(const std::string& key, size_t value_size, std::chrono::nanoseconds latency);
    void record_delete(const std::string& key);
    void record_eviction(const std::string& key);
    void record_expiration(const std::string& key);

    // Update memory metrics (called periodically)
    void update_memory_metrics(const MemoryMetrics& metrics);

    // Get current snapshot
    AnalyticsSnapshot get_snapshot() const;

    // Get hot keys (sorted by access count, descending)
    std::vector<HotKeyEntry> get_hot_keys(size_t limit = 10) const;

    // Get latency percentile (0.0 to 1.0)
    std::chrono::nanoseconds get_latency_percentile(double percentile) const;

    // Configuration
    void set_config(const AnalyticsConfig& config);
    void enable();
    void disable();
    bool is_enabled() const;

    // Reset all statistics
    void reset();

    // Register export sink
    void add_sink(std::shared_ptr<IAnalyticsSink> sink);

    // Export to all registered sinks
    void export_now();

    // Start periodic export (runs in background thread)
    void start_periodic_export(std::chrono::seconds interval);
    void stop_periodic_export();

private:
    AnalyticsConfig config_;
    std::vector<std::shared_ptr<IAnalyticsSink>> sinks_;
    std::atomic<bool> enabled_{true};
    std::atomic<bool> exporting_{false};
    std::thread export_thread_;
    mutable std::mutex mutex_;

    // Counters (atomic for lock-free increment)
    std::atomic<uint64_t> total_gets_{0};
    std::atomic<uint64_t> total_sets_{0};
    std::atomic<uint64_t> total_deletes_{0};
    std::atomic<uint64_t> total_evictions_{0};
    std::atomic<uint64_t> total_expirations_{0};
    std::atomic<uint64_t> cache_hits_{0};
    std::atomic<uint64_t> cache_misses_{0};

    // Latency histogram
    std::vector<LatencyBucket> latency_histogram_;

    // Hot key tracking (needs mutex protection)
    std::unordered_map<std::string, std::atomic<uint64_t>> key_access_counts_;
    std::chrono::steady_clock::time_point start_time_;

    // Memory metrics (updated periodically)
    MemoryMetrics memory_metrics_;

    void initialize_histogram();
    void record_latency(std::chrono::nanoseconds latency);
    void increment_key_access(const std::string& key);
    void prune_cold_keys();
};

// RAII latency timer for automatic recording
class ScopedLatencyTimer {
public:
    ScopedLatencyTimer(CacheAnalytics& analytics, CacheOperation op, const std::string& key);
    ~ScopedLatencyTimer();

    void set_hit(bool hit);
    void set_value_size(size_t size);

private:
    CacheAnalytics& analytics_;
    CacheOperation operation_;
    std::string key_;
    std::chrono::steady_clock::time_point start_;
    bool hit_ = false;
    size_t value_size_ = 0;
};

}  // namespace cacheforge

#endif  // CACHEFORGE_CACHE_ANALYTICS_H
```

### Required Files

| File | Description |
|------|-------------|
| `src/analytics/cache_analytics.h` | Interface definitions (above) |
| `src/analytics/cache_analytics.cpp` | Main collector implementation |
| `src/analytics/json_sink.cpp` | JSON file export sink |
| `tests/unit/test_analytics.cpp` | Unit tests (25+ test cases) |
| `tests/integration/test_analytics_integration.cpp` | Integration with HashTable |

### Implementation Requirements

1. **Low Overhead**: Recording operations should be fast (sub-microsecond). Use atomics for counters, batch updates where possible.

2. **Thread Safety**: Multiple threads will call record_* methods concurrently. Use lock-free atomics for counters.

3. **Memory Bounded**: Hot key tracking must be bounded. Prune cold keys when limit exceeded.

4. **Accurate Percentiles**: Use a histogram with logarithmic buckets for latency distribution. Interpolate for exact percentiles.

5. **Rolling Window**: Statistics should reflect the configured sampling window, not all-time totals.

6. **Export Pattern**: Follow the sink pattern for extensibility. JSON sink must produce valid JSON.

### Acceptance Criteria

- [ ] All 25+ unit tests pass
- [ ] Hit rate calculation is accurate
- [ ] Latency percentiles within 5% of actual
- [ ] Hot key tracking correctly identifies top-N keys
- [ ] Memory metrics update correctly
- [ ] JSON export produces valid, parseable JSON
- [ ] Periodic export runs reliably
- [ ] Thread safety verified with ThreadSanitizer
- [ ] Recording overhead < 500ns per operation

### Test Cases to Implement

```cpp
// tests/unit/test_analytics.cpp
TEST(AnalyticsTest, test_record_get_hit);
TEST(AnalyticsTest, test_record_get_miss);
TEST(AnalyticsTest, test_hit_rate_calculation);
TEST(AnalyticsTest, test_record_set_with_size);
TEST(AnalyticsTest, test_record_delete);
TEST(AnalyticsTest, test_record_eviction);
TEST(AnalyticsTest, test_record_expiration);
TEST(AnalyticsTest, test_latency_histogram_buckets);
TEST(AnalyticsTest, test_latency_percentile_p50);
TEST(AnalyticsTest, test_latency_percentile_p95);
TEST(AnalyticsTest, test_latency_percentile_p99);
TEST(AnalyticsTest, test_hot_key_tracking);
TEST(AnalyticsTest, test_hot_key_limit_pruning);
TEST(AnalyticsTest, test_memory_metrics_update);
TEST(AnalyticsTest, test_snapshot_generation);
TEST(AnalyticsTest, test_reset_clears_all);
TEST(AnalyticsTest, test_enable_disable);
TEST(AnalyticsTest, test_json_sink_output);
TEST(AnalyticsTest, test_periodic_export);
TEST(AnalyticsTest, test_concurrent_recording);
TEST(AnalyticsTest, test_scoped_timer);
TEST(AnalyticsTest, test_empty_snapshot);
TEST(AnalyticsTest, test_rolling_window);
TEST(AnalyticsTest, test_multiple_sinks);
TEST(AnalyticsTest, test_export_thread_safety);
```

---

## General Guidelines

### Following Existing Patterns

1. **Namespacing**: All code in `namespace cacheforge { }`

2. **Header Guards**: Use both `#pragma once` and traditional guards:
   ```cpp
   #pragma once
   #ifndef CACHEFORGE_MODULE_NAME_H
   #define CACHEFORGE_MODULE_NAME_H
   // ...
   #endif  // CACHEFORGE_MODULE_NAME_H
   ```

3. **Thread Safety**: Use `std::mutex` with `std::lock_guard` or `std::unique_lock`. Use `std::atomic` for simple counters. See `eviction.h` and `hashtable.h` patterns.

4. **Atomic Flags**: Use `std::atomic<bool>` for running/enabled flags, not `volatile`. See `server.h` for the bug example to avoid.

5. **Memory Management**: Use `std::unique_ptr` and `std::shared_ptr`. Avoid raw `new`/`delete`. See `snapshot.h` for RAII patterns.

6. **Error Handling**: Return `std::optional` or `bool` for fallible operations. Don't throw exceptions in hot paths.

### CMake Integration

Add new modules to `CMakeLists.txt`:

```cmake
# In src/CMakeLists.txt
add_library(cacheforge_lib
    # ... existing sources ...
    warming/cache_warmer.cpp
    compression/compression_pipeline.cpp
    compression/lz4_compressor.cpp
    analytics/cache_analytics.cpp
    analytics/json_sink.cpp
)

# In tests/CMakeLists.txt
add_executable(unit_tests
    # ... existing tests ...
    unit/test_cache_warmer.cpp
    unit/test_compression.cpp
    unit/test_analytics.cpp
)

add_executable(integration_tests
    # ... existing tests ...
    integration/test_warming_integration.cpp
    integration/test_compression_integration.cpp
    integration/test_analytics_integration.cpp
)
```

### Verification Checklist

Before submitting, verify:

- [ ] All new tests pass: `ctest --test-dir build --output-on-failure`
- [ ] No compiler warnings: `cmake --build build 2>&1 | grep -i warning`
- [ ] ThreadSanitizer clean: `cmake -DCMAKE_CXX_FLAGS="-fsanitize=thread" -B build-tsan && cmake --build build-tsan && ctest --test-dir build-tsan`
- [ ] AddressSanitizer clean: `cmake -DCMAKE_CXX_FLAGS="-fsanitize=address" -B build-asan && cmake --build build-asan && ctest --test-dir build-asan`
- [ ] Code follows existing naming conventions
- [ ] Public interfaces are documented with comments
