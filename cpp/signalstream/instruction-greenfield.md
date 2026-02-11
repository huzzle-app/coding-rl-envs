# SignalStream - Greenfield Tasks

## Overview

These tasks require implementing new modules from scratch within the SignalStream signal processing platform. Each task builds upon existing architecture patterns found in `include/signalstream/core.hpp` and integrates with the service infrastructure. Implement complete signal processing capabilities including frequency-domain analysis, correlation detection, and advanced alerting.

## Environment

- **Language**: C++20
- **Infrastructure**: Kafka, PostgreSQL, Redis, InfluxDB, etcd
- **Difficulty**: Apex-Principal
- **Build System**: CMake with CTest

## Tasks

### Task 1: FFT Processing Pipeline

Implement a Fast Fourier Transform (FFT) processing pipeline that transforms time-domain signals into frequency-domain representations. Create the `IFFTProcessor` interface with implementations for batch and streaming (overlap-add) processing. Support multiple window functions (Rectangular, Hanning, Hamming, Blackman, Kaiser) for spectral analysis. Return `SpectrumResult` objects containing frequency bins with magnitude, phase, and power calculations. Integrate with `IngestBuffer` for input and `StorageEngine` for persisting spectral data.

**Key Interface**: `include/signalstream/fft.hpp` with `IFFTProcessor`, `SpectrumResult`, `FrequencyBin`, and window function support.

### Task 2: Signal Correlation Engine

Implement a cross-correlation engine for detecting signal similarity, time delays, and pattern matching. Create the `ICorrelationEngine` interface supporting both auto-correlation (signal with itself) and cross-correlation (between two signals). Implement direct computation for small signals and FFT-based methods for large signals. Return `CorrelationResult` with lag analysis and `PatternMatch` objects for pattern detection. Support three output modes (FULL, SAME, VALID) and proper zero-mean normalization using Kahan summation following existing `Aggregator` patterns.

**Key Interface**: `include/signalstream/correlation.hpp` with `ICorrelationEngine`, `CorrelationResult`, `PatternMatch`, and correlation mode support.

### Task 3: Alert Rule Evaluator

Implement an advanced alert rule evaluator supporting complex conditional expressions and stateful rule evaluation. Create the `IRuleEvaluator` interface with support for simple and composite rules using AND/OR/NOT logical operators. Implement a DSL parser for rule expressions like `"cpu_usage.avg(300) > 80"` and `"(cpu > 80) AND (memory > 90)"`. Support aggregation functions (LAST, AVG, SUM, MIN, MAX, COUNT, STDDEV, PERCENTILE_95, RATE), cooldown periods, and consecutive trigger requirements for flapping detection.

**Key Interface**: `include/signalstream/rule_evaluator.hpp` with `IRuleEvaluator`, `RuleCondition`, `CompositeRule`, `EvaluationResult`, and DSL parsing utilities.

## Getting Started

```bash
# Clean build
rm -rf build
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel

# Run all tests
cd build && ctest --output-on-failure

# Run only greenfield module tests
ctest --test-dir build --output-on-failure -R "fft_|correlation_|rule_"
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). Each task includes:
- Complete header interface definitions in `include/signalstream/`
- Concrete implementations in `src/`
- Comprehensive unit tests added to `tests/test_main.cpp`
- CMakeLists.txt integration for new source files and test cases
- Thread-safe design using `std::mutex` and RAII patterns
- Full adherence to existing SignalStream architecture conventions
