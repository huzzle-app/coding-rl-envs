# GridWeaver - Greenfield Implementation Tasks

## Overview

Three greenfield implementation tasks that extend GridWeaver with new capabilities: machine learning-ready load forecasting, renewable energy optimization, and real-time fault detection. Each task requires implementing a new module from scratch while integrating with existing architectural patterns and maintaining thread-safety guarantees.

## Environment

- **Language**: Go
- **Infrastructure**: Distributed smart-grid platform with NATS JetStream, PostgreSQL, Redis, InfluxDB, and etcd
- **Difficulty**: Ultra-Principal (8-threshold reward)

## Tasks

### Task 1: Load Forecasting Service ([Greenfield](./TASKS_GREENFIELD.md#task-1-load-forecasting-service))

Implement a machine learning-ready load forecasting service in `internal/loadforecast/predictor.go` that predicts power demand with confidence intervals. The service must provide probabilistic forecasts, support concurrent training requests, compute forecast accuracy metrics, and integrate with the estimator package using shared `models.MeterReading` types.

**Interface highlights:**
- `Predictor` interface with `Predict()`, `TrainModel()`, `GetModelStats()`, `ComparePredictions()`
- `LoadPrediction` with confidence bounds (upper/lower at 95% CI)
- `ForecastInput` aggregating historical data, weather forecasts, and active programs
- `ModelStats` and `AccuracyReport` for performance tracking

**Key patterns:** Thread-safe with `sync.RWMutex`, return slice copies to prevent mutation, use `models.MeterReading` from shared types.

### Task 2: Renewable Integration Optimizer ([Greenfield](./TASKS_GREENFIELD.md#task-2-renewable-integration-optimizer))

Implement a renewable energy integration optimizer in `internal/renewable/optimizer.go` that balances intermittent renewable supply against demand while maintaining grid stability. The optimizer must coordinate with dispatch, respect transmission constraints from topology, and intelligently schedule storage charge/discharge cycles to maximize renewable utilization.

**Interface highlights:**
- `Optimizer` interface with `OptimizeIntegration()`, `GenerateCurtailmentOrders()`, `CalculateRenewablePenetration()`, `ForecastIntegration()`, `OptimalStorageDispatch()`
- `RenewableSource` with current output, forecasts, and ramp rate limits
- `StorageAsset` for batteries and pumped hydro with efficiency models
- `GridConstraints` defining operational limits
- `IntegrationPlan` and `StorageAction` for dispatch instructions

**Key patterns:** Sort curtailment orders by source priority (avoid BUG(E06) boundary errors), validate ramp rates, use proper floating-point division (avoid BUG(E03) integer truncation).

### Task 3: Grid Fault Detector ([Greenfield](./TASKS_GREENFIELD.md#task-3-grid-fault-detector))

Implement a fault detection service in `internal/faultdetector/detector.go` that monitors grid telemetry for anomalies and triggers protective actions. The detector must identify equipment failures across multiple sensor types, correlate related faults by time and topology, and emit events compatible with the events pipeline.

**Interface highlights:**
- `Detector` interface with `ProcessTelemetry()`, `GetActiveAlerts()`, `AcknowledgeAlert()`, `GetNodeHealth()`, `TriggerProtectiveAction()`, `CorrelateAlerts()`, `EmitFaultEvent()`
- `TelemetryReading` with quality indicator (ignore readings where Quality < 0.5)
- `FaultAlert` with severity levels (1-4) and acknowledgment tracking
- `DetectionThresholds` for voltage, current, frequency, temperature
- `ProtectiveAction` for automated responses (isolate, reduce_load, trip_breaker, alert)
- `NodeHealth` tracking composite health score

**Key patterns:** Thread-safe with `sync.RWMutex`, return copies of internal state, use signed deviation for frequency (avoid BUG(H02) absolute value), include boundary values in threshold checks (avoid BUG(E01) off-by-one).

## Getting Started

```bash
docker compose up -d
go test -race -v ./...
bash harbor/test.sh
```

## Success Criteria

All tasks must achieve 90%+ test coverage with unit tests in `tests/unit/` directory. Code must pass `go test -race -v ./...` without data race warnings. Integration tests should verify interaction with existing services (estimator, topology, dispatch, events, outage). Edge cases must be handled gracefully (empty inputs, null checks, boundary conditions).

Implementation must follow existing GridWeaver patterns: use `sync.RWMutex` for thread-safety, return copies of slices, validate inputs, handle errors with descriptive messages (no panics), and integrate with the shared `contracts.GridEvent` type for event emission.
