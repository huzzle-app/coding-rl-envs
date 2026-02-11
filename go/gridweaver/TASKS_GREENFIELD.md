# GridWeaver - Greenfield Implementation Tasks

This document defines greenfield implementation tasks for extending the GridWeaver smart grid orchestration platform. Each task requires implementing a new module from scratch while following the existing architectural patterns.

**Test Command:** `go test -v ./...`

---

## Task 1: Load Forecasting Service

### Overview

Implement a machine learning-ready load forecasting service that predicts power demand across grid regions. The service must integrate with the existing `forecast` service and `estimator` internal package to provide probabilistic demand predictions with confidence intervals.

### Interface Contract

Create the file `internal/loadforecast/predictor.go`:

```go
package loadforecast

import (
    "time"
    "gridweaver/pkg/models"
)

// ForecastHorizon defines the prediction time range.
type ForecastHorizon struct {
    Start    time.Time
    End      time.Time
    StepMins int // prediction step granularity (e.g., 15, 30, 60)
}

// LoadPrediction represents a single demand forecast point.
type LoadPrediction struct {
    Timestamp   time.Time
    Region      string
    PredictedMW float64
    LowerBound  float64 // 95% confidence interval lower bound
    UpperBound  float64 // 95% confidence interval upper bound
    Confidence  float64 // model confidence score 0.0-1.0
}

// ForecastInput contains all inputs needed for load prediction.
type ForecastInput struct {
    Region           string
    HistoricalLoads  []models.MeterReading // past meter readings
    TemperatureForecast []TemperaturePoint
    WindForecast     []WindPoint
    HolidayFlags     []bool                // true for holidays in prediction window
    ActiveDRPrograms int                   // number of active demand response programs
}

// TemperaturePoint is a temperature forecast at a specific time.
type TemperaturePoint struct {
    Timestamp    time.Time
    TemperatureC float64
}

// WindPoint is a wind forecast at a specific time.
type WindPoint struct {
    Timestamp time.Time
    WindPct   float64
}

// Predictor generates load forecasts for grid regions.
type Predictor interface {
    // Predict generates load predictions for the given horizon.
    // Returns one LoadPrediction per time step in the horizon.
    Predict(input ForecastInput, horizon ForecastHorizon) ([]LoadPrediction, error)

    // TrainModel updates the prediction model with new historical data.
    // Must be thread-safe for concurrent training requests.
    TrainModel(region string, readings []models.MeterReading) error

    // GetModelStats returns model performance metrics for a region.
    GetModelStats(region string) (ModelStats, error)

    // ComparePredictions evaluates forecast accuracy against actuals.
    ComparePredictions(predictions []LoadPrediction, actuals []models.MeterReading) AccuracyReport
}

// ModelStats contains model performance metrics.
type ModelStats struct {
    Region          string
    LastTrainedAt   time.Time
    SampleCount     int
    MAPE            float64 // Mean Absolute Percentage Error
    RMSE            float64 // Root Mean Square Error
    BiasPercent     float64 // systematic over/under prediction
}

// AccuracyReport summarizes forecast performance.
type AccuracyReport struct {
    Region         string
    PeriodStart    time.Time
    PeriodEnd      time.Time
    TotalPoints    int
    WithinBounds   int     // predictions where actual was within confidence interval
    AvgErrorMW     float64
    MaxErrorMW     float64
    AvgConfidence  float64
}
```

### Required Structs

| Struct | Purpose |
|--------|---------|
| `ForecastHorizon` | Defines prediction time window and granularity |
| `LoadPrediction` | Single forecast point with confidence bounds |
| `ForecastInput` | Aggregates all prediction inputs |
| `TemperaturePoint` | Temperature forecast at a timestamp |
| `WindPoint` | Wind forecast at a timestamp |
| `ModelStats` | Model performance metrics |
| `AccuracyReport` | Forecast accuracy summary |

### Architectural Requirements

1. **Follow existing patterns:**
   - Use `sync.RWMutex` for thread-safe model access (see `internal/topology/graph.go`)
   - Return copies of slices to prevent caller mutation (unlike `BUG(B01)` in dispatch service)
   - Use the `pkg/models` package for shared types

2. **Integration points:**
   - Consume `models.MeterReading` from the estimator package
   - Produce events compatible with `contracts.GridEvent`
   - Support the same region identifiers used in `models.RegionState`

3. **Numerical stability:**
   - Use Kahan summation for aggregating large datasets (avoid `BUG(D02)` pattern)
   - Preserve floating-point precision (avoid int truncation like `BUG(D13)`)
   - Validate inputs are non-negative where appropriate

### Acceptance Criteria

- [ ] Unit tests in `tests/unit/loadforecast_test.go` with 90%+ coverage
- [ ] Prediction accuracy test: forecasts within 10% MAPE on synthetic test data
- [ ] Thread-safety test: concurrent `TrainModel` and `Predict` calls with `-race` flag
- [ ] Integration test: consume readings from estimator, produce predictions
- [ ] Edge cases: empty inputs, single reading, readings with `Quality < 0.5`
- [ ] All tests pass with `go test -race -v ./...`

---

## Task 2: Renewable Integration Optimizer

### Overview

Implement a renewable energy integration optimizer that maximizes the use of solar and wind generation while maintaining grid stability. The service must balance intermittent renewable supply against demand, coordinate with the dispatch solver, and respect transmission constraints from the topology package.

### Interface Contract

Create the file `internal/renewable/optimizer.go`:

```go
package renewable

import (
    "time"
    "gridweaver/pkg/models"
    "gridweaver/internal/topology"
)

// RenewableSource represents a renewable generation asset.
type RenewableSource struct {
    ID           string
    Region       string
    Type         string  // "solar", "wind", "hydro"
    CapacityMW   float64
    CurrentMW    float64 // current generation
    ForecastMW   []float64 // predicted generation for next N intervals
    RampRateMW   float64 // max change per minute
    Priority     int     // dispatch priority (higher = prefer)
}

// CurtailmentOrder instructs a renewable source to reduce output.
type CurtailmentOrder struct {
    SourceID     string
    TargetMW     float64
    Reason       string // "oversupply", "congestion", "stability"
    IssuedAt     time.Time
    ExpiresAt    time.Time
}

// IntegrationPlan describes how to balance renewables with demand.
type IntegrationPlan struct {
    Region           string
    Timestamp        time.Time
    TotalRenewableMW float64
    CurtailmentMW    float64
    StorageChargeMW  float64 // excess to store
    StorageDischargeMW float64 // deficit from storage
    ConventionalMW   float64 // backup generation needed
    StabilityMargin  float64 // 0.0-1.0 safety margin
}

// StorageAsset represents a battery or pumped hydro facility.
type StorageAsset struct {
    ID              string
    Region          string
    CapacityMWh     float64
    CurrentMWh      float64
    MaxChargeMW     float64
    MaxDischargeMW  float64
    Efficiency      float64 // round-trip efficiency 0.0-1.0
}

// GridConstraints defines operational limits.
type GridConstraints struct {
    MinStabilityMargin float64 // minimum reserve margin
    MaxRampRateMW      float64 // max grid-wide ramp rate
    TransmissionLimit  float64 // max inter-region transfer
}

// Optimizer coordinates renewable integration into the grid.
type Optimizer interface {
    // OptimizeIntegration creates an integration plan for the current period.
    // Balances renewable supply against demand while respecting constraints.
    OptimizeIntegration(
        sources []RenewableSource,
        storage []StorageAsset,
        demandMW float64,
        constraints GridConstraints,
    ) (IntegrationPlan, error)

    // GenerateCurtailmentOrders creates curtailment instructions when needed.
    // Returns orders sorted by source priority (lowest priority curtailed first).
    GenerateCurtailmentOrders(
        sources []RenewableSource,
        excessMW float64,
        graph *topology.Graph,
    ) []CurtailmentOrder

    // CalculateRenewablePenetration computes the percentage of demand met by renewables.
    CalculateRenewablePenetration(plan IntegrationPlan) float64

    // ForecastIntegration predicts integration challenges for the next N periods.
    // Returns one IntegrationPlan per period.
    ForecastIntegration(
        sources []RenewableSource,
        storage []StorageAsset,
        demandForecast []float64,
        constraints GridConstraints,
    ) ([]IntegrationPlan, error)

    // OptimalStorageDispatch determines when to charge/discharge storage.
    // Maximizes renewable utilization and minimizes curtailment.
    OptimalStorageDispatch(
        storage StorageAsset,
        renewableForecast []float64,
        demandForecast []float64,
        periods int,
    ) []StorageAction
}

// StorageAction describes a charge or discharge instruction.
type StorageAction struct {
    Period       int
    ActionType   string  // "charge", "discharge", "idle"
    PowerMW      float64
    ExpectedMWh  float64 // state of charge after action
}
```

### Required Structs

| Struct | Purpose |
|--------|---------|
| `RenewableSource` | Renewable generation asset with forecast |
| `CurtailmentOrder` | Instruction to reduce renewable output |
| `IntegrationPlan` | Renewable-demand balance plan |
| `StorageAsset` | Battery/pumped hydro storage facility |
| `GridConstraints` | Operational limits for optimization |
| `StorageAction` | Storage charge/discharge instruction |

### Architectural Requirements

1. **Follow existing patterns:**
   - Use sort patterns from `internal/dispatch/solver.go` for priority ordering
   - Integrate with `topology.Graph` for transmission constraints
   - Use `models.DispatchPlan` for conventional generation coordination

2. **Constraint validation:**
   - Respect `GridConstraints.MinStabilityMargin` (see `estimator.StabilityMargin`)
   - Validate ramp rates (avoid `BUG(E06)` boundary errors)
   - Check transmission capacity using `topology.ValidateTransfer`

3. **Numerical precision:**
   - Use proper division (avoid `BUG(E03)` integer division)
   - Handle efficiency losses correctly (avoid `BUG(D09)` ratio inversion)
   - Maintain precision in aggregations (avoid `BUG(D05)` weighted average errors)

### Acceptance Criteria

- [ ] Unit tests in `tests/unit/renewable_test.go` with 90%+ coverage
- [ ] Optimization test: correctly maximizes renewable usage while meeting demand
- [ ] Curtailment test: orders sorted by priority, lowest first
- [ ] Storage optimization: correctly schedules charge/discharge cycles
- [ ] Integration test: works with topology graph for congestion detection
- [ ] Edge cases: no renewables, 100% renewable, storage full/empty
- [ ] All tests pass with `go test -race -v ./...`

---

## Task 3: Grid Fault Detector

### Overview

Implement a fault detection service that monitors grid telemetry for anomalies, detects potential equipment failures, and triggers protective actions. The service must integrate with the events pipeline, outage service, and resilience patterns to provide real-time grid health monitoring.

### Interface Contract

Create the file `internal/faultdetector/detector.go`:

```go
package faultdetector

import (
    "sync"
    "time"
    "gridweaver/pkg/models"
    "gridweaver/shared/contracts"
)

// TelemetryReading represents a sensor measurement from grid equipment.
type TelemetryReading struct {
    NodeID      string
    SensorType  string    // "voltage", "current", "frequency", "temperature"
    Value       float64
    Unit        string
    Timestamp   time.Time
    Quality     float64   // 0.0-1.0 data quality indicator
}

// FaultType categorizes detected faults.
type FaultType string

const (
    FaultTypeOvervoltage    FaultType = "overvoltage"
    FaultTypeUndervoltage   FaultType = "undervoltage"
    FaultTypeOvercurrent    FaultType = "overcurrent"
    FaultTypeFrequencyDev   FaultType = "frequency_deviation"
    FaultTypeOverheat       FaultType = "overheat"
    FaultTypeEquipmentFail  FaultType = "equipment_failure"
    FaultTypeLineTrip       FaultType = "line_trip"
)

// FaultAlert represents a detected fault condition.
type FaultAlert struct {
    ID           string
    NodeID       string
    Region       string
    FaultType    FaultType
    Severity     int       // 1=minor, 2=moderate, 3=major, 4=critical
    DetectedAt   time.Time
    Value        float64   // the measurement that triggered the alert
    Threshold    float64   // the threshold that was exceeded
    Description  string
    Acknowledged bool
}

// DetectionThresholds defines limits for each sensor type.
type DetectionThresholds struct {
    VoltageMinPU     float64 // per-unit voltage minimum (e.g., 0.95)
    VoltageMaxPU     float64 // per-unit voltage maximum (e.g., 1.05)
    CurrentMaxPU     float64 // per-unit current maximum (e.g., 1.2)
    FrequencyMinHz   float64 // minimum frequency (e.g., 59.5)
    FrequencyMaxHz   float64 // maximum frequency (e.g., 60.5)
    TemperatureMaxC  float64 // maximum equipment temperature
}

// ProtectiveAction describes an automated response to a fault.
type ProtectiveAction struct {
    ID           string
    FaultID      string
    ActionType   string    // "isolate", "reduce_load", "trip_breaker", "alert_operator"
    TargetNodeID string
    Parameters   map[string]string
    ExecutedAt   time.Time
    Success      bool
    Message      string
}

// NodeHealth tracks the health status of a grid node.
type NodeHealth struct {
    NodeID           string
    Region           string
    IsHealthy        bool
    LastSeen         time.Time
    ActiveFaults     int
    RecentAlerts     int       // alerts in last hour
    HealthScore      float64   // 0.0-1.0 composite health score
}

// Detector monitors grid telemetry and detects faults.
type Detector interface {
    // ProcessTelemetry ingests a telemetry reading and checks for faults.
    // Returns any detected fault alerts (may be empty if reading is normal).
    // Must be thread-safe for concurrent telemetry ingestion.
    ProcessTelemetry(reading TelemetryReading, thresholds DetectionThresholds) []FaultAlert

    // GetActiveAlerts returns all unacknowledged fault alerts.
    // Thread-safe read of internal alert state.
    GetActiveAlerts() []FaultAlert

    // AcknowledgeAlert marks an alert as acknowledged by an operator.
    AcknowledgeAlert(alertID string) error

    // GetNodeHealth returns current health status for a node.
    GetNodeHealth(nodeID string) (NodeHealth, error)

    // TriggerProtectiveAction executes an automated response to a fault.
    // Must validate the action is appropriate for the fault severity.
    TriggerProtectiveAction(alert FaultAlert) (ProtectiveAction, error)

    // CorrelateAlerts identifies related faults that may share a root cause.
    // Groups alerts by time window and topology proximity.
    CorrelateAlerts(alerts []FaultAlert, windowSecs int) [][]FaultAlert

    // EmitFaultEvent creates a GridEvent for the event pipeline.
    EmitFaultEvent(alert FaultAlert) contracts.GridEvent
}

// DetectorImpl is the concrete implementation of Detector.
type DetectorImpl struct {
    mu           sync.RWMutex
    alerts       map[string]FaultAlert
    nodeHealth   map[string]*NodeHealth
    eventHistory []contracts.GridEvent
}

// NewDetector creates a new fault detector instance.
func NewDetector() *DetectorImpl {
    return &DetectorImpl{
        alerts:       make(map[string]FaultAlert),
        nodeHealth:   make(map[string]*NodeHealth),
        eventHistory: []contracts.GridEvent{},
    }
}
```

### Required Structs

| Struct | Purpose |
|--------|---------|
| `TelemetryReading` | Sensor measurement from grid equipment |
| `FaultAlert` | Detected fault condition |
| `DetectionThresholds` | Limits for each sensor type |
| `ProtectiveAction` | Automated fault response |
| `NodeHealth` | Health status of a grid node |

### Architectural Requirements

1. **Follow existing patterns:**
   - Use `sync.RWMutex` for thread-safe state (see `topology.Graph`)
   - Acquire mutex before modifying internal state (avoid `BUG(A08)` race conditions)
   - Return copies of internal slices (avoid `BUG(B01)` caller mutation)

2. **Event integration:**
   - Produce `contracts.GridEvent` compatible with the events pipeline
   - Use proper correlation IDs for related events
   - Support idempotency keys for deduplication

3. **Outage coordination:**
   - Alert severity should map to `models.OutageReport.Priority`
   - Protective actions should produce outage reports when isolating nodes
   - Track active outages using the outage service pattern

4. **Data quality:**
   - Ignore readings with `Quality < 0.5` (see `estimator.QualityIndex`)
   - Use signed deviation for frequency (avoid `BUG(H02)` absolute value)
   - Include boundary values in threshold checks (avoid `BUG(E01)` off-by-one)

### Acceptance Criteria

- [ ] Unit tests in `tests/unit/faultdetector_test.go` with 90%+ coverage
- [ ] Threshold detection: correctly identifies all fault types
- [ ] Thread-safety: concurrent `ProcessTelemetry` calls with `-race` flag
- [ ] Alert correlation: groups related faults by time and proximity
- [ ] Protective actions: validates severity before executing
- [ ] Event emission: produces valid `GridEvent` with proper fields
- [ ] Edge cases: low quality readings, rapid successive faults, node recovery
- [ ] Integration test: works with outage service and events pipeline
- [ ] All tests pass with `go test -race -v ./...`

---

## General Guidelines

### Code Organization

Follow the existing package structure:

```
gridweaver/
├── internal/
│   ├── loadforecast/    # Task 1
│   │   └── predictor.go
│   ├── renewable/       # Task 2
│   │   └── optimizer.go
│   └── faultdetector/   # Task 3
│       └── detector.go
├── tests/
│   └── unit/
│       ├── loadforecast_test.go
│       ├── renewable_test.go
│       └── faultdetector_test.go
└── pkg/models/
    └── models.go        # Add new shared types here if needed
```

### Common Patterns to Follow

1. **Constructor pattern:** Use `New()` function returning the concrete type
2. **Mutex guards:** Always acquire lock before modifying shared state
3. **Slice safety:** Return copies, not references to internal slices
4. **Input validation:** Check for nil slices, negative values, division by zero
5. **Error handling:** Return descriptive errors, don't panic

### Common Bugs to Avoid

| Bug Pattern | Example | Correct Approach |
|------------|---------|------------------|
| Missing mutex | `BUG(A08)` in dispatch | Always `Lock()`/`Unlock()` |
| Slice reference leak | `BUG(B01)` in dispatch | Return `copy()` of slice |
| Boundary off-by-one | `BUG(E01)` in topology | Use `>=` not `>` for limits |
| Integer truncation | `BUG(D13)` in dispatch | Keep `float64` throughout |
| Inverted ratio | `BUG(D09)` in demandresponse | `delivered/requested`, not reverse |
| Wrong division | `BUG(D05)` in estimator | Divide by sum of weights |
