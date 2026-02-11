# ChronoMesh Greenfield Tasks

These tasks require implementing new modules from scratch within the ChronoMesh time-series data platform. Each task must follow existing architectural patterns observed in the codebase.

---

## Task 1: Downsampling Engine

### Overview

Implement a downsampling engine that reduces time-series data granularity for long-term storage and efficient querying. The engine should support multiple aggregation strategies and configurable retention windows.

### Interface Contract

Add to `include/chronomesh/core.hpp`:

```cpp
namespace chronomesh {

// ---------------------------------------------------------------------------
// Downsampling types
// ---------------------------------------------------------------------------

enum class AggregationStrategy {
  AVERAGE,
  MIN,
  MAX,
  SUM,
  LAST,
  FIRST
};

struct DataPoint {
  long long timestamp_ms;
  double value;
  std::string metric_id;
};

struct DownsampledBucket {
  long long start_ms;
  long long end_ms;
  double value;
  int sample_count;
  std::string metric_id;
};

struct DownsampleConfig {
  int source_interval_ms;
  int target_interval_ms;
  AggregationStrategy strategy;
  bool preserve_extremes;  // Keep min/max within bucket
};

struct DownsampleResult {
  std::vector<DownsampledBucket> buckets;
  int original_count;
  int output_count;
  double compression_ratio;
};

// ---------------------------------------------------------------------------
// Downsampling functions
// ---------------------------------------------------------------------------

DownsampledBucket aggregate_bucket(const std::vector<DataPoint>& points,
                                    long long start_ms, long long end_ms,
                                    AggregationStrategy strategy);

DownsampleResult downsample(const std::vector<DataPoint>& points,
                            const DownsampleConfig& config);

bool validate_downsample_config(const DownsampleConfig& config);

int calculate_bucket_count(long long time_range_ms, int target_interval_ms);

// ---------------------------------------------------------------------------
// Downsampler class (stateful)
// ---------------------------------------------------------------------------

class Downsampler {
public:
  explicit Downsampler(const DownsampleConfig& config);

  void ingest(const DataPoint& point);
  std::vector<DownsampledBucket> flush();
  DownsampledBucket* current_bucket();
  int pending_count();
  void reset();
  DownsampleConfig config() const;

private:
  std::mutex mu_;
  DownsampleConfig config_;
  std::map<std::string, std::vector<DataPoint>> pending_;
  std::vector<DownsampledBucket> completed_;
};

class MultiResolutionStore {
public:
  MultiResolutionStore();

  void add_resolution(const std::string& name, DownsampleConfig config);
  void ingest(const DataPoint& point);
  std::vector<DownsampledBucket> query(const std::string& resolution,
                                        const std::string& metric_id,
                                        long long start_ms, long long end_ms);
  std::map<std::string, int> bucket_counts();
  void compact(const std::string& resolution);
  void reset();

private:
  mutable std::shared_mutex mu_;
  std::map<std::string, Downsampler> downsamplers_;
  std::map<std::string, std::vector<DownsampledBucket>> storage_;
};

}  // namespace chronomesh
```

### Implementation Requirements

Create `src/downsampling.cpp` with:

1. **aggregate_bucket()**: Apply aggregation strategy to points within time window
2. **downsample()**: Partition points into buckets and aggregate each
3. **validate_downsample_config()**: Ensure target_interval >= source_interval, strategy valid
4. **calculate_bucket_count()**: Compute expected bucket count for time range
5. **Downsampler class**: Streaming ingestion with automatic bucket completion
6. **MultiResolutionStore class**: Multiple downsampling resolutions (1m, 5m, 1h, 1d)

### Architectural Patterns to Follow

- Use `std::mutex` for single-threaded mutation (see `RollingWindowScheduler`)
- Use `std::shared_mutex` for read-heavy concurrent access (see `RouteTable`)
- Return pointers for optional results, `nullptr` when not found (see `PriorityQueue::peek()`)
- Thread-safe stateful classes with private mutex members
- Pure functions for stateless operations

### Acceptance Criteria

1. **Unit Tests** (add to CMakeLists.txt):
   - `downsample_average`: Test AVERAGE aggregation with 10 points -> 2 buckets
   - `downsample_min_max`: Test MIN and MAX strategies preserve extremes
   - `downsample_empty`: Handle empty input gracefully
   - `downsample_config_validation`: Reject invalid configs (target < source)
   - `downsampler_streaming`: Ingest 100 points, verify flush produces correct buckets
   - `multi_resolution_query`: Store at 1m/5m/1h, query each resolution

2. **Integration Points**:
   - `ResponseTimeTracker` feeds data to `Downsampler` for long-term latency trends
   - `Downsampler` respects `RateLimiter` when ingesting high-volume streams

3. **Test Command**:
   ```bash
   cmake --build build && ctest --test-dir build --output-on-failure
   ```

---

## Task 2: Retention Policy Enforcer

### Overview

Implement a retention policy system that automatically expires and purges time-series data based on configurable rules. Supports tiered retention (hot/warm/cold), metric-specific overrides, and space-based quotas.

### Interface Contract

Add to `include/chronomesh/core.hpp`:

```cpp
namespace chronomesh {

// ---------------------------------------------------------------------------
// Retention types
// ---------------------------------------------------------------------------

enum class RetentionTier {
  HOT,    // Real-time, full resolution
  WARM,   // Recent, may be downsampled
  COLD,   // Archive, heavily compressed
  EXPIRED // Marked for deletion
};

struct RetentionRule {
  std::string metric_pattern;  // Glob pattern (e.g., "cpu.*", "*.latency")
  int hot_retention_hours;
  int warm_retention_hours;
  int cold_retention_hours;
  int priority;  // Higher priority rules override lower
};

struct RetentionPolicy {
  std::string policy_id;
  std::vector<RetentionRule> rules;
  long long max_storage_bytes;
  double emergency_purge_ratio;  // Purge when storage exceeds this ratio
};

struct DataSegment {
  std::string segment_id;
  std::string metric_id;
  long long start_ms;
  long long end_ms;
  long long size_bytes;
  RetentionTier tier;
};

struct PurgeDecision {
  bool should_purge;
  std::string reason;
  RetentionTier current_tier;
  RetentionTier target_tier;
};

struct EnforcementResult {
  int segments_evaluated;
  int segments_promoted;
  int segments_demoted;
  int segments_purged;
  long long bytes_freed;
};

// ---------------------------------------------------------------------------
// Retention functions
// ---------------------------------------------------------------------------

RetentionTier calculate_tier(const DataSegment& segment,
                             const RetentionRule& rule,
                             long long now_ms);

PurgeDecision evaluate_segment(const DataSegment& segment,
                               const RetentionPolicy& policy,
                               long long now_ms);

bool matches_pattern(const std::string& metric_id, const std::string& pattern);

RetentionRule* find_matching_rule(const std::string& metric_id,
                                  const std::vector<RetentionRule>& rules);

std::string validate_retention_policy(const RetentionPolicy& policy);

// ---------------------------------------------------------------------------
// RetentionEnforcer class
// ---------------------------------------------------------------------------

class RetentionEnforcer {
public:
  explicit RetentionEnforcer(const RetentionPolicy& policy);

  void register_segment(const DataSegment& segment);
  void remove_segment(const std::string& segment_id);
  EnforcementResult enforce(long long now_ms);
  std::vector<DataSegment> segments_by_tier(RetentionTier tier);
  long long total_storage_bytes();
  bool is_over_quota();
  std::vector<std::string> pending_purge_ids();
  void apply_purge(const std::vector<std::string>& segment_ids);
  void update_policy(const RetentionPolicy& policy);
  RetentionPolicy current_policy() const;
  void reset();

private:
  std::mutex mu_;
  RetentionPolicy policy_;
  std::map<std::string, DataSegment> segments_;
  std::vector<std::string> purge_queue_;
};

class TieredStorageManager {
public:
  TieredStorageManager();

  void configure_tier(RetentionTier tier, long long max_bytes);
  bool store(const DataSegment& segment, RetentionTier tier);
  bool migrate(const std::string& segment_id, RetentionTier from, RetentionTier to);
  std::vector<DataSegment> query_tier(RetentionTier tier);
  std::map<RetentionTier, long long> usage_by_tier();
  bool evict_lru(RetentionTier tier, long long bytes_needed);
  void reset();

private:
  mutable std::shared_mutex mu_;
  std::map<RetentionTier, long long> tier_limits_;
  std::map<RetentionTier, std::vector<DataSegment>> tier_storage_;
  std::map<RetentionTier, long long> tier_usage_;
};

}  // namespace chronomesh
```

### Implementation Requirements

Create `src/retention.cpp` with:

1. **calculate_tier()**: Determine segment tier based on age and rule thresholds
2. **evaluate_segment()**: Full purge decision including quota checks
3. **matches_pattern()**: Glob-style pattern matching for metric IDs
4. **find_matching_rule()**: Find highest-priority matching rule
5. **validate_retention_policy()**: Ensure rules are valid, quotas positive
6. **RetentionEnforcer class**: Stateful enforcement with segment tracking
7. **TieredStorageManager class**: LRU eviction and tier migration

### Architectural Patterns to Follow

- Return empty string for valid, error message for invalid (see `validate_order()`)
- Use `PolicyChange`-style audit records for tier migrations
- State machine pattern for tier transitions (HOT -> WARM -> COLD -> EXPIRED)
- Thread-safe with granular locking (see `TokenStore`)

### Acceptance Criteria

1. **Unit Tests** (add to CMakeLists.txt):
   - `retention_tier_calculation`: Verify age-based tier assignment
   - `retention_pattern_matching`: Test glob patterns ("cpu.*", "*.p99")
   - `retention_rule_priority`: Higher priority rules override lower
   - `retention_quota_enforcement`: Trigger purge when over quota
   - `retention_enforcer_lifecycle`: Register, enforce, purge segments
   - `tiered_storage_migration`: Migrate segments between tiers
   - `tiered_storage_lru_eviction`: Evict oldest when tier full

2. **Integration Points**:
   - `CheckpointManager` checkpoints include retention tier metadata
   - `PolicyEngine` can trigger emergency retention mode under load

3. **Test Command**:
   ```bash
   cmake --build build && ctest --test-dir build --output-on-failure
   ```

---

## Task 3: Anomaly Detection Pipeline

### Overview

Implement a streaming anomaly detection pipeline for time-series metrics. Supports statistical methods (z-score, IQR), rate-of-change detection, and pattern-based anomalies with configurable sensitivity.

### Interface Contract

Add to `include/chronomesh/core.hpp`:

```cpp
namespace chronomesh {

// ---------------------------------------------------------------------------
// Anomaly detection types
// ---------------------------------------------------------------------------

enum class AnomalyType {
  NONE,
  SPIKE,          // Sudden increase
  DROP,           // Sudden decrease
  DEVIATION,      // Outside normal range
  RATE_CHANGE,    // Abnormal rate of change
  MISSING_DATA,   // Gap in expected data
  PATTERN_BREAK   // Deviation from seasonal pattern
};

enum class DetectionMethod {
  ZSCORE,         // Standard deviation based
  IQR,            // Interquartile range
  ROLLING_MEAN,   // Moving average deviation
  RATE_OF_CHANGE, // First derivative threshold
  EXPONENTIAL_SMOOTHING  // EMA-based
};

struct AnomalyConfig {
  DetectionMethod method;
  double sensitivity;       // 0.0 = very sensitive, 1.0 = very tolerant
  int window_size;          // Lookback window for baseline
  int min_data_points;      // Minimum points before detection starts
  bool ignore_nulls;
};

struct Anomaly {
  std::string anomaly_id;
  std::string metric_id;
  long long detected_at_ms;
  AnomalyType type;
  double value;
  double expected_value;
  double deviation_score;    // How abnormal (higher = more severe)
  std::string description;
};

struct DetectionResult {
  bool is_anomaly;
  AnomalyType type;
  double score;
  double threshold;
  double baseline_mean;
  double baseline_stddev;
};

struct AnomalyStats {
  int total_points_processed;
  int anomalies_detected;
  double anomaly_rate;
  std::map<AnomalyType, int> anomalies_by_type;
};

// ---------------------------------------------------------------------------
// Anomaly detection functions
// ---------------------------------------------------------------------------

DetectionResult detect_zscore(const std::vector<double>& baseline,
                               double current_value,
                               double sensitivity);

DetectionResult detect_iqr(std::vector<double> baseline,
                            double current_value,
                            double sensitivity);

DetectionResult detect_rate_of_change(const std::vector<double>& recent_values,
                                       double sensitivity);

double calculate_ema(const std::vector<double>& values, double alpha);

AnomalyType classify_anomaly(double current, double expected,
                              double threshold, double rate_of_change);

std::string validate_anomaly_config(const AnomalyConfig& config);

// ---------------------------------------------------------------------------
// AnomalyDetector class
// ---------------------------------------------------------------------------

class AnomalyDetector {
public:
  explicit AnomalyDetector(const AnomalyConfig& config);

  DetectionResult ingest(const std::string& metric_id, double value, long long timestamp_ms);
  std::vector<Anomaly> get_anomalies(const std::string& metric_id);
  std::vector<Anomaly> get_recent_anomalies(long long since_ms);
  void clear_anomalies(const std::string& metric_id);
  AnomalyStats stats();
  void update_config(const AnomalyConfig& config);
  AnomalyConfig current_config() const;
  void reset();

private:
  std::mutex mu_;
  AnomalyConfig config_;
  std::map<std::string, std::vector<double>> baselines_;
  std::map<std::string, std::vector<Anomaly>> anomalies_;
  AnomalyStats stats_;
};

class AnomalyPipeline {
public:
  AnomalyPipeline();

  void add_detector(const std::string& name, AnomalyConfig config);
  void remove_detector(const std::string& name);
  std::vector<Anomaly> process(const std::string& metric_id,
                                double value, long long timestamp_ms);
  void subscribe(const std::string& detector_name,
                 std::function<void(const Anomaly&)> callback);
  std::map<std::string, AnomalyStats> all_stats();
  void suppress_metric(const std::string& metric_id, long long until_ms);
  bool is_suppressed(const std::string& metric_id, long long now_ms);
  void reset();

private:
  mutable std::shared_mutex mu_;
  std::map<std::string, AnomalyDetector> detectors_;
  std::map<std::string, std::vector<std::function<void(const Anomaly&)>>> subscribers_;
  std::map<std::string, long long> suppressions_;
};

}  // namespace chronomesh
```

### Implementation Requirements

Create `src/anomaly.cpp` with:

1. **detect_zscore()**: Z-score detection with configurable threshold
2. **detect_iqr()**: Interquartile range outlier detection
3. **detect_rate_of_change()**: First derivative spike detection
4. **calculate_ema()**: Exponential moving average for smoothing
5. **classify_anomaly()**: Map deviation to anomaly type
6. **validate_anomaly_config()**: Validate sensitivity [0,1], window > 0
7. **AnomalyDetector class**: Single-method streaming detector
8. **AnomalyPipeline class**: Multi-detector with callbacks and suppression

### Architectural Patterns to Follow

- Use callback pattern for async notification (see `std::function` usage)
- Statistics tracking pattern (see `ResponseTimeTracker`)
- Suppression/cooldown pattern (see `CircuitBreaker` recovery time)
- Audit log for detected anomalies (see `WorkflowEngine::audit_log()`)

### Acceptance Criteria

1. **Unit Tests** (add to CMakeLists.txt):
   - `anomaly_zscore_detection`: Detect value 3+ stddev from mean
   - `anomaly_iqr_detection`: Detect values outside 1.5*IQR
   - `anomaly_rate_of_change`: Detect sudden spikes
   - `anomaly_classification`: Correct type assignment (SPIKE vs DROP)
   - `anomaly_detector_streaming`: Ingest 1000 points with 5 injected anomalies
   - `anomaly_pipeline_multi_detector`: Run zscore + iqr in parallel
   - `anomaly_suppression`: Verify suppressed metrics don't alert
   - `anomaly_config_validation`: Reject invalid sensitivity values

2. **Integration Points**:
   - `ResponseTimeTracker` feeds latency data to `AnomalyDetector`
   - `CircuitBreaker` opens on repeated anomalies in same metric
   - `PolicyEngine` escalates when anomaly rate exceeds threshold

3. **Test Command**:
   ```bash
   cmake --build build && ctest --test-dir build --output-on-failure
   ```

---

## General Implementation Notes

### File Structure

After implementation, the source tree should include:

```
cpp/chronomesh/
  include/chronomesh/
    core.hpp           # Extended with new types and declarations
  src/
    allocator.cpp      # Existing
    routing.cpp        # Existing
    ...
    downsampling.cpp   # NEW
    retention.cpp      # NEW
    anomaly.cpp        # NEW
  tests/
    test_main.cpp      # Extended with new test cases
  CMakeLists.txt       # Extended with new source files and tests
```

### CMakeLists.txt Updates

Add new source files to the library:

```cmake
add_library(chronomesh
  src/allocator.cpp
  src/routing.cpp
  # ... existing files ...
  src/downsampling.cpp
  src/retention.cpp
  src/anomaly.cpp
)
```

Add test entries for each new test case.

### Code Style

- 
- Follow existing namespace structure (`namespace chronomesh { ... }`)
- Use C++20 features (designated initializers, ranges where applicable)
- Prefer `std::map` over `std::unordered_map` for deterministic iteration
- Use `static_cast<>` for numeric type conversions

### Thread Safety

- All stateful classes must be thread-safe
- Use `std::mutex` for exclusive access
- Use `std::shared_mutex` for read-heavy workloads
- Document locking strategy in class comments
