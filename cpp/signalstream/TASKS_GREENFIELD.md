# SignalStream Greenfield Tasks

These tasks require implementing NEW modules from scratch within the SignalStream signal processing platform. Each task builds upon the existing architecture patterns found in `include/signalstream/core.hpp` and the source files in `src/`.

---

## Task 1: FFT Processing Pipeline

### Overview

Implement a Fast Fourier Transform (FFT) processing pipeline that transforms time-domain signals into frequency-domain representations. This module integrates with the existing `IngestBuffer` for input and `StorageEngine` for persistence of spectral data.

### Interface Contract

Create `include/signalstream/fft.hpp` with the following abstract interface:

```cpp
#pragma once

#include "signalstream/core.hpp"
#include <complex>
#include <span>

namespace signalstream {

// Frequency bin result from FFT analysis
struct FrequencyBin {
    double frequency_hz;      // Center frequency of the bin
    double magnitude;         // Absolute magnitude
    double phase_radians;     // Phase angle
    double power_db;          // Power in decibels
};

// Complete spectrum result
struct SpectrumResult {
    std::string signal_id;
    int64_t timestamp;
    double sample_rate_hz;
    size_t fft_size;
    std::vector<FrequencyBin> bins;
    double dc_component;
    double nyquist_frequency;
};

// Window functions for spectral analysis
enum class WindowFunction {
    RECTANGULAR,
    HANNING,
    HAMMING,
    BLACKMAN,
    KAISER
};

// Abstract FFT processor interface
class IFFTProcessor {
public:
    virtual ~IFFTProcessor() = default;

    // Configure the FFT processor
    virtual void configure(size_t fft_size, double sample_rate_hz,
                          WindowFunction window = WindowFunction::HANNING) = 0;

    // Process a batch of time-domain samples
    virtual SpectrumResult process(const std::string& signal_id,
                                   std::span<const double> samples,
                                   int64_t timestamp) = 0;

    // Process streaming data with overlap-add method
    virtual void process_streaming(const std::string& signal_id,
                                   std::span<const double> samples,
                                   double overlap_ratio,
                                   std::function<void(const SpectrumResult&)> callback) = 0;

    // Get current configuration
    virtual size_t fft_size() const = 0;
    virtual double sample_rate() const = 0;
    virtual WindowFunction window() const = 0;
};

// Factory function
std::unique_ptr<IFFTProcessor> create_fft_processor();

// Utility functions
std::vector<double> apply_window(std::span<const double> samples, WindowFunction window);
double frequency_to_bin(double frequency_hz, double sample_rate_hz, size_t fft_size);
double bin_to_frequency(size_t bin_index, double sample_rate_hz, size_t fft_size);

}  // namespace signalstream
```

### Required Classes/Structs

| Component | Description |
|-----------|-------------|
| `FrequencyBin` | Single frequency bin result with magnitude, phase, and power |
| `SpectrumResult` | Complete spectrum analysis output |
| `WindowFunction` | Enum for supported window types |
| `IFFTProcessor` | Abstract processor interface |
| `FFTProcessor` | Concrete implementation in `src/fft.cpp` |

### Implementation Requirements

1. **FFT Algorithm**: Implement Cooley-Tukey radix-2 FFT (or use optimized bit-reversal permutation)
2. **Thread Safety**: All public methods must be thread-safe with appropriate mutex guards
3. **Memory Management**: Use RAII for all resources; no raw `new`/`delete`
4. **Window Functions**: Implement at least RECTANGULAR, HANNING, and HAMMING windows
5. **Streaming Support**: Overlap-add method for continuous signal processing
6. **Error Handling**: Validate FFT size is power of 2; throw `std::invalid_argument` otherwise

### Integration Points

- Input: `DataPoint` values from `IngestBuffer` (convert `double value` to sample array)
- Output: Store `SpectrumResult` via `StorageEngine` with key format `spectrum:{signal_id}:{timestamp}`
- Telemetry: Register metrics via `Telemetry::record_metric()` for FFT processing latency

### Acceptance Criteria

1. **Unit Tests** (add to `tests/test_main.cpp`):
   - `fft_basic_transform`: FFT of known sinusoid produces expected peak at correct frequency
   - `fft_window_functions`: Each window function produces correct coefficients
   - `fft_power_spectrum`: Power calculation in dB is mathematically correct
   - `fft_streaming_overlap`: Streaming mode produces consistent results with batch mode
   - `fft_thread_safety`: Concurrent calls to `process()` are safe
   - `fft_invalid_size`: Non-power-of-2 FFT size throws exception

2. **CMakeLists.txt Updates**:
   - Add `src/fft.cpp` to the library sources
   - Add test cases to CTest

3. **Test Command**:
   ```bash
   cmake --build build && ctest --test-dir build --output-on-failure -R "fft_"
   ```

---

## Task 2: Signal Correlation Engine

### Overview

Implement a cross-correlation engine for comparing signal similarity, detecting time delays, and identifying patterns across multiple data streams. This module supports both auto-correlation (signal with itself) and cross-correlation (between two signals).

### Interface Contract

Create `include/signalstream/correlation.hpp`:

```cpp
#pragma once

#include "signalstream/core.hpp"
#include <span>

namespace signalstream {

// Correlation result with lag information
struct CorrelationResult {
    std::string signal_a_id;
    std::string signal_b_id;      // Empty for auto-correlation
    int64_t timestamp;
    std::vector<double> coefficients;   // Correlation coefficients at each lag
    int optimal_lag;                     // Lag with maximum correlation
    double max_correlation;              // Peak correlation value
    double normalized_max;               // Normalized to [-1, 1] range
    bool is_autocorrelation;
};

// Pattern match result
struct PatternMatch {
    std::string signal_id;
    int64_t start_timestamp;
    int64_t end_timestamp;
    double correlation_score;
    int lag_samples;
};

// Correlation computation mode
enum class CorrelationMode {
    FULL,       // Full correlation: output size = N + M - 1
    SAME,       // Same size as larger input
    VALID       // Only where signals fully overlap
};

// Abstract correlation engine interface
class ICorrelationEngine {
public:
    virtual ~ICorrelationEngine() = default;

    // Compute cross-correlation between two signals
    virtual CorrelationResult cross_correlate(
        const std::string& signal_a_id,
        std::span<const double> signal_a,
        const std::string& signal_b_id,
        std::span<const double> signal_b,
        CorrelationMode mode = CorrelationMode::FULL) = 0;

    // Compute auto-correlation of a signal
    virtual CorrelationResult auto_correlate(
        const std::string& signal_id,
        std::span<const double> signal,
        int max_lag = -1) = 0;

    // Find time delay between signals (in samples)
    virtual int find_delay(
        std::span<const double> reference,
        std::span<const double> delayed) = 0;

    // Search for pattern occurrences in signal
    virtual std::vector<PatternMatch> find_pattern(
        const std::string& signal_id,
        std::span<const double> signal,
        std::span<const double> pattern,
        double min_correlation = 0.8) = 0;

    // Normalize correlation coefficients to [-1, 1]
    virtual void normalize(CorrelationResult& result) = 0;

    // Configure FFT-based correlation for large signals
    virtual void set_fft_threshold(size_t min_samples_for_fft) = 0;
};

// Factory function
std::unique_ptr<ICorrelationEngine> create_correlation_engine();

// Utility functions
double pearson_correlation(std::span<const double> x, std::span<const double> y);
double covariance(std::span<const double> x, std::span<const double> y);
std::vector<double> sliding_correlation(std::span<const double> signal,
                                        std::span<const double> window,
                                        size_t stride = 1);

}  // namespace signalstream
```

### Required Classes/Structs

| Component | Description |
|-----------|-------------|
| `CorrelationResult` | Full correlation output with lag analysis |
| `PatternMatch` | Location and score of pattern matches |
| `CorrelationMode` | Enum for output size modes |
| `ICorrelationEngine` | Abstract engine interface |
| `CorrelationEngine` | Concrete implementation in `src/correlation.cpp` |

### Implementation Requirements

1. **Algorithm Selection**: Use direct computation for small signals; FFT-based for signals larger than threshold
2. **Normalization**: Implement proper zero-mean normalization for Pearson correlation
3. **Memory Efficiency**: Avoid copying large signal data; use views/spans where possible
4. **Thread Safety**: Support concurrent correlations on different signal pairs
5. **Precision**: Use Kahan summation (following `Aggregator` pattern) for accumulations
6. **Edge Cases**: Handle signals of different lengths, empty signals, constant signals

### Integration Points

- Input: Signal data from `query_range()` or `StorageEngine::get()`
- Output: Store `CorrelationResult` with key format `correlation:{signal_a}:{signal_b}:{timestamp}`
- Alerts: Trigger `AlertService` when correlation drops below configured threshold
- Telemetry: Track correlation computation time and cache hit rates

### Acceptance Criteria

1. **Unit Tests**:
   - `correlation_identical_signals`: Auto-correlation of signal with itself has max at lag 0
   - `correlation_delayed_signal`: Cross-correlation correctly identifies time delay
   - `correlation_pattern_match`: Pattern finder locates known pattern with correct score
   - `correlation_normalize`: Normalized coefficients are in [-1, 1] range
   - `correlation_modes`: FULL, SAME, VALID modes produce correct output sizes
   - `correlation_fft_equivalence`: FFT-based result matches direct computation
   - `correlation_pearson`: Pearson coefficient matches expected value for known data

2. **CMakeLists.txt Updates**:
   - Add `src/correlation.cpp` to library sources
   - Add test cases to CTest

3. **Test Command**:
   ```bash
   cmake --build build && ctest --test-dir build --output-on-failure -R "correlation_"
   ```

---

## Task 3: Alert Rule Evaluator

### Overview

Implement an advanced alert rule evaluator that supports complex conditional expressions, composite rules, and stateful evaluation. This extends the existing `AlertService` with a domain-specific language (DSL) for defining sophisticated alerting conditions.

### Interface Contract

Create `include/signalstream/rule_evaluator.hpp`:

```cpp
#pragma once

#include "signalstream/core.hpp"
#include <variant>

namespace signalstream {

// Comparison operators for rule conditions
enum class ComparisonOp {
    EQUAL,
    NOT_EQUAL,
    GREATER_THAN,
    GREATER_EQUAL,
    LESS_THAN,
    LESS_EQUAL
};

// Logical operators for combining conditions
enum class LogicalOp {
    AND,
    OR,
    NOT
};

// Aggregation functions for time-window evaluation
enum class AggregateFunc {
    LAST,           // Most recent value
    FIRST,          // First value in window
    AVG,            // Average over window
    SUM,            // Sum over window
    MIN,            // Minimum in window
    MAX,            // Maximum in window
    COUNT,          // Count of values
    STDDEV,         // Standard deviation
    PERCENTILE_95,  // 95th percentile
    RATE            // Rate of change per second
};

// Single condition in a rule
struct RuleCondition {
    std::string signal_id;
    AggregateFunc aggregate;
    int64_t window_seconds;        // Time window for aggregation
    ComparisonOp comparison;
    double threshold;
};

// Forward declaration for recursive variant
struct CompositeRule;

// Rule expression type (either simple or composite)
using RuleExpr = std::variant<RuleCondition, std::shared_ptr<CompositeRule>>;

// Composite rule combining multiple expressions
struct CompositeRule {
    LogicalOp op;
    std::vector<RuleExpr> children;
};

// Evaluation result with details
struct EvaluationResult {
    std::string rule_id;
    bool triggered;
    int64_t evaluated_at;
    std::string trigger_reason;        // Human-readable explanation
    std::unordered_map<std::string, double> computed_values;  // signal_id -> aggregated value
    int consecutive_triggers;          // For flapping detection
};

// Rule with metadata
struct EvaluatorRule {
    std::string rule_id;
    std::string name;
    std::string description;
    RuleExpr expression;
    std::string severity;              // "critical", "warning", "info"
    int cooldown_seconds;              // Minimum time between alerts
    int required_consecutive;          // Must trigger N times consecutively
    std::vector<std::string> labels;   // For grouping/routing
};

// Abstract rule evaluator interface
class IRuleEvaluator {
public:
    virtual ~IRuleEvaluator() = default;

    // Register a rule for evaluation
    virtual void register_rule(const EvaluatorRule& rule) = 0;

    // Unregister a rule
    virtual void unregister_rule(const std::string& rule_id) = 0;

    // Evaluate a single rule against current signal data
    virtual EvaluationResult evaluate_rule(
        const std::string& rule_id,
        const std::unordered_map<std::string, std::vector<DataPoint>>& signals) = 0;

    // Evaluate all registered rules
    virtual std::vector<EvaluationResult> evaluate_all(
        const std::unordered_map<std::string, std::vector<DataPoint>>& signals) = 0;

    // Parse rule expression from string DSL
    // Format: "signal.aggregate(window) op threshold"
    // Example: "cpu_usage.avg(300) > 80"
    // Composite: "(cpu_usage.avg(300) > 80) AND (memory.max(60) > 90)"
    virtual RuleExpr parse_expression(const std::string& dsl) = 0;

    // Serialize rule expression to string
    virtual std::string serialize_expression(const RuleExpr& expr) = 0;

    // Get evaluation history for a rule
    virtual std::vector<EvaluationResult> get_history(
        const std::string& rule_id,
        int64_t start_time,
        int64_t end_time) = 0;

    // Check if rule is in cooldown
    virtual bool is_in_cooldown(const std::string& rule_id) const = 0;

    // Get all registered rules
    virtual std::vector<EvaluatorRule> list_rules() const = 0;
};

// Factory function
std::unique_ptr<IRuleEvaluator> create_rule_evaluator();

// DSL parsing utilities
RuleCondition parse_condition(const std::string& expr);
AggregateFunc parse_aggregate_func(const std::string& name);
ComparisonOp parse_comparison_op(const std::string& op);

}  // namespace signalstream
```

### Required Classes/Structs

| Component | Description |
|-----------|-------------|
| `ComparisonOp` | Enum for comparison operators |
| `LogicalOp` | Enum for logical combining operators |
| `AggregateFunc` | Enum for aggregation functions |
| `RuleCondition` | Single evaluation condition |
| `CompositeRule` | Recursive rule structure for AND/OR/NOT |
| `RuleExpr` | Variant type for rule expressions |
| `EvaluationResult` | Detailed evaluation output |
| `EvaluatorRule` | Complete rule with metadata |
| `IRuleEvaluator` | Abstract evaluator interface |
| `RuleEvaluator` | Concrete implementation in `src/rule_evaluator.cpp` |

### Implementation Requirements

1. **DSL Parser**: Implement recursive descent parser for rule expressions
2. **Aggregation**: Reuse `Aggregator` class methods where applicable; ensure NaN handling
3. **State Management**: Track consecutive triggers, cooldown periods, evaluation history
4. **Thread Safety**: All rule registration/evaluation must be thread-safe
5. **Memory Management**: Use `std::shared_ptr` for recursive rule structures
6. **Performance**: Cache aggregated values within same evaluation cycle
7. **Error Handling**: Provide clear error messages for parse failures

### Integration Points

- Input: Signal data from `query_range()` function
- Output: Generate `AlertEvent` objects compatible with existing `AlertService`
- Storage: Persist evaluation history via `StorageEngine`
- Config: Rules can be loaded from `ConfigEntry` variant values
- Telemetry: Track evaluation latency, trigger rates per rule

### Acceptance Criteria

1. **Unit Tests**:
   - `rule_simple_threshold`: Basic threshold rule evaluates correctly
   - `rule_composite_and`: AND composite rule requires all conditions
   - `rule_composite_or`: OR composite rule triggers on any condition
   - `rule_composite_not`: NOT inverts child rule result
   - `rule_aggregate_functions`: Each aggregate function computes correctly
   - `rule_dsl_parse`: DSL string parses to correct expression tree
   - `rule_dsl_roundtrip`: Parse then serialize produces equivalent string
   - `rule_cooldown`: Rule in cooldown does not re-trigger
   - `rule_consecutive`: Requires N consecutive triggers before alerting
   - `rule_thread_safety`: Concurrent evaluations are safe

2. **CMakeLists.txt Updates**:
   - Add `src/rule_evaluator.cpp` to library sources
   - Add test cases to CTest

3. **Test Command**:
   ```bash
   cmake --build build && ctest --test-dir build --output-on-failure -R "rule_"
   ```

---

## General Implementation Guidelines

### Following Existing Patterns

1. **Header Organization**: Single header in `include/signalstream/` with implementation in `src/`
2. **Namespace**: All code in `signalstream` namespace
3. **Error Handling**: Use exceptions for invalid input; return `std::optional` for "not found" cases
4. **Threading**: Use `std::mutex` with `std::lock_guard`; follow `Aggregator` and `StorageEngine` patterns
5. **Naming**: PascalCase for types, snake_case for functions/variables
6. **Constants**: Use `constexpr` where possible; define in header

### Build Integration

Add new source files to `CMakeLists.txt`:

```cmake
add_library(signalstream
  # ... existing sources ...
  src/fft.cpp
  src/correlation.cpp
  src/rule_evaluator.cpp
)
```

### Test Integration

Add test cases following the existing pattern in `tests/test_main.cpp`:

```cpp
// In main() dispatch:
else if (name == "fft_basic_transform") ok = fft_basic_transform();
else if (name == "correlation_identical_signals") ok = correlation_identical_signals();
else if (name == "rule_simple_threshold") ok = rule_simple_threshold();
// ... etc
```

Add corresponding CTest entries:

```cmake
add_test(NAME fft_basic_transform COMMAND signalstream_tests fft_basic_transform)
add_test(NAME correlation_identical_signals COMMAND signalstream_tests correlation_identical_signals)
add_test(NAME rule_simple_threshold COMMAND signalstream_tests rule_simple_threshold)
```

### Running All Greenfield Tests

```bash
# Build the project
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build

# Run all tests
ctest --test-dir build --output-on-failure

# Run only greenfield module tests
ctest --test-dir build --output-on-failure -R "fft_|correlation_|rule_"
```
