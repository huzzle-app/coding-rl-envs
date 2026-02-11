# ChronoMesh - Greenfield Tasks

## Overview

These three greenfield tasks require implementing new modules from scratch within the ChronoMesh time-series platform. Each task builds functionality that integrates with existing systems while following established architectural patterns. These tasks test your ability to design clean interfaces, implement thread-safe stateful components, and integrate new modules into a complex system.

## Environment

- **Language**: C++20
- **Infrastructure**: Docker-based testing with CMake build system
- **Difficulty**: Hyper-Principal (70-140 hours)

## Tasks

### Task 1: Downsampling Engine (Greenfield Implementation)

Implement a downsampling engine that reduces time-series data granularity for long-term storage and efficient querying. Create a `Downsampler` class supporting multiple aggregation strategies (AVERAGE, MIN, MAX, SUM, LAST, FIRST) with configurable retention windows. Implement a `MultiResolutionStore` that manages multiple downsampling resolutions (1-minute, 5-minute, 1-hour, 1-day) with streaming ingestion, automatic bucket completion, and queryable time-range access. The engine must integrate with the existing `ResponseTimeTracker` for latency aggregations while respecting the `RateLimiter` for high-volume streams.

**Key Interface Components:**
- `struct AggregationStrategy`: Enum for aggregation type selection
- `struct DataPoint`: Time-series data point with timestamp, value, and metric_id
- `struct DownsampledBucket`: Result bucket with aggregated data and metadata
- `class Downsampler`: Streaming ingestion with automatic bucket completion
- `class MultiResolutionStore`: Multi-resolution storage with configurable resolutions

### Task 2: Retention Policy Enforcer (Greenfield Implementation)

Implement a retention policy system that automatically expires and purges time-series data based on configurable rules. Build a `RetentionEnforcer` class that manages tiered retention (HOT/WARM/COLD/EXPIRED) with metric-specific pattern matching, space-based quotas, and emergency purge triggers. Implement a `TieredStorageManager` that handles segment migration between tiers, LRU eviction when quotas are exceeded, and state machine transitions through retention lifecycle. The system must support glob-style pattern matching for metric IDs, priority-based rule resolution, and integration with the `CheckpointManager` for audit metadata.

**Key Interface Components:**
- `enum class RetentionTier`: HOT, WARM, COLD, EXPIRED states
- `struct RetentionRule`: Pattern-based rules with per-tier retention windows
- `struct DataSegment`: Tracked storage unit with size and tier metadata
- `class RetentionEnforcer`: Segment registration, enforcement, and purge decisions
- `class TieredStorageManager`: Tier management with LRU eviction

### Task 3: Anomaly Detection Pipeline (Greenfield Implementation)

Implement a streaming anomaly detection pipeline for time-series metrics supporting multiple statistical detection methods. Create an `AnomalyDetector` class implementing z-score, IQR (Interquartile Range), rolling mean, rate-of-change, and exponential smoothing methods with configurable sensitivity. Build an `AnomalyPipeline` that chains multiple detectors, supports callback-based notification, metric-level suppression/cooldown, and integration with the `CircuitBreaker` for repeated anomalies. Classify detected anomalies into types (SPIKE, DROP, DEVIATION, RATE_CHANGE, MISSING_DATA, PATTERN_BREAK) and track statistics per metric and detector.

**Key Interface Components:**
- `enum class AnomalyType`: Classification types (SPIKE, DROP, DEVIATION, etc.)
- `enum class DetectionMethod`: ZSCORE, IQR, ROLLING_MEAN, RATE_OF_CHANGE, EXPONENTIAL_SMOOTHING
- `struct AnomalyConfig`: Configurable detection method, sensitivity, window size
- `struct Anomaly`: Detected anomaly with classification, score, and metadata
- `class AnomalyDetector`: Single-method streaming detector with baseline tracking
- `class AnomalyPipeline`: Multi-detector with callbacks and metric suppression

## Getting Started

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug && cmake --build build && ctest --test-dir build --output-on-failure
```

## Implementation Guidance

All new modules must:

1. **Follow Architectural Patterns**:
   - Use `std::mutex` for single-threaded mutation
   - Use `std::shared_mutex` for read-heavy concurrent access
   - Return pointers for optional results, `nullptr` when not found
   - Pure functions for stateless operations

2. **Integrate with Existing Systems**:
   - Add new types/declarations to `include/chronomesh/core.hpp`
   - Create implementation in new `src/*.cpp` files
   - Update `CMakeLists.txt` with new source files and test cases
   - Follow existing code style (C++20, designated initializers, `std::map` for determinism)

3. **Provide Thread Safety**:
   - Document locking strategy in class comments
   - Use consistent synchronization patterns across all classes
   - Minimize critical section time for contended resources

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) for the chosen task, including:

- All specified unit tests passing (downsample/retention/anomaly specific tests)
- Integration points functioning correctly with existing systems
- Thread-safe operations with no race conditions
- Memory-efficient designs with bounded resource usage
- Full test suite passing without modification to test files
