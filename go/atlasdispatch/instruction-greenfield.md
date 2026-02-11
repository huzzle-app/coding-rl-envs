# AtlasDispatch - Greenfield Tasks

## Overview

This document describes three greenfield implementation tasks for the AtlasDispatch maritime dispatch and routing platform. These tasks require implementing new modules from scratch that integrate with the existing codebase while testing software design and interface implementation skills.

## Environment

- **Language**: Go
- **Infrastructure**: Maritime dispatch system with routing, allocation, event replay, and security modules
- **Difficulty**: Hyper-Principal
- **Test Command**: `go test -v ./...`

## Tasks

### Task 1: Proof of Delivery Service (Greenfield Implementation)

Implement a proof of delivery (POD) service that captures delivery confirmations, signatures, photos, and timestamps. This service integrates with the workflow engine to transition orders to "completed" state upon successful delivery confirmation.

**Package Location**: Create `internal/delivery/delivery.go`

**Interface Contract**:

The service must implement the following interface and types:

```go
type DeliveryProof struct {
    ID            string
    OrderID       string
    RecipientName string
    SignatureHash string    // SHA256 hash of signature data
    PhotoHash     string    // SHA256 hash of photo data (optional)
    Location      Location
    Timestamp     time.Time
    Status        ProofStatus
    Notes         string
}

type Location struct {
    Lat       float64
    Lng       float64
    Accuracy  float64 // meters
    Timestamp time.Time
}

type ProofStatus string // "pending", "validated", "rejected", "expired"

type ValidationResult struct {
    Valid           bool
    Reason          string
    LocationMatch   bool
    TimestampValid  bool
    SignatureValid  bool
}

type DeliveryProofService interface {
    SubmitProof(proof DeliveryProof) error
    ValidateProof(proofID string, destLat, destLng float64, maxRadiusM float64, windowMinutes int) ValidationResult
    GetProof(proofID string) *DeliveryProof
    GetProofByOrder(orderID string) *DeliveryProof
    ListPendingProofs() []DeliveryProof
    ExpireStaleProofs(maxAge time.Duration) int
    UpdateStatus(proofID string, status ProofStatus, reason string) error
    ProofStats() ProofStatistics
}

type ProofStatistics struct {
    TotalProofs     int
    PendingCount    int
    ValidatedCount  int
    RejectedCount   int
    ExpiredCount    int
    AvgValidationMs float64
}
```

**Required Helper Functions**:
- `CalculateDistance()` - Haversine formula for coordinate distance
- `ValidateSignatureHash()` - SHA256 hex format validation
- `IsWithinTimeWindow()` - Timestamp window checking
- `GenerateProofID()` - Unique proof ID generation

**Acceptance Criteria**:
1. Unit tests in `tests/unit/delivery_test.go` covering proof submission, location distance calculations, time window validation, signature hashing, concurrent submissions, stale proof expiration, and statistics accuracy
2. Integration with `security.Digest()` for hash verification
3. Service registrable in `shared/contracts/contracts.go`
4. Status changes loggable for audit trail
5. Minimum 80% line coverage for the delivery package

---

### Task 2: Dynamic Rerouting Engine (Greenfield Implementation)

Implement a dynamic rerouting engine that recomputes optimal routes when conditions change (traffic, weather, vehicle breakdowns). The engine should maintain route state, detect when rerouting is beneficial, and integrate with the existing routing module.

**Package Location**: Create `internal/reroute/reroute.go`

**Interface Contract**:

The service must implement the following interface and types:

```go
type RouteCondition struct {
    SegmentID     string
    ConditionType ConditionType  // "traffic", "weather", "incident", "closure", "hazmat"
    Severity      int            // 1-5
    DelayMinutes  int
    ReportedAt    time.Time
    ExpiresAt     time.Time
    Source        string         // "traffic", "weather", "incident", "manual"
}

type RerouteDecision struct {
    ShouldReroute     bool
    OriginalETA       time.Time
    NewETA            time.Time
    TimeSavedMinutes  int
    CostDelta         float64
    AffectedSegments  []string
    AlternativeRoute  []RouteSegment
    Confidence        float64     // 0.0-1.0
    Reason            string
}

type RouteSegment struct {
    ID             string
    FromLocation   string
    ToLocation     string
    DistanceKm     float64
    BaseTimeMin    int
    CurrentTimeMin int
}

type ActiveRoute struct {
    ID               string
    OrderID          string
    Segments         []RouteSegment
    CurrentSegment   int
    StartedAt        time.Time
    EstimatedArrival time.Time
    LastUpdated      time.Time
}

type ConditionStatistics struct {
    ActiveConditions   int
    ConditionsByType   map[ConditionType]int
    AvgSeverity        float64
    TotalDelayMinutes  int
    AffectedRoutes     int
}

type RerouteEngine interface {
    RegisterRoute(route ActiveRoute) error
    UnregisterRoute(routeID string) error
    ReportCondition(condition RouteCondition) error
    ClearCondition(segmentID string, conditionType ConditionType) error
    EvaluateReroute(routeID string, minTimeSavings int, maxCostIncrease float64) RerouteDecision
    GetActiveConditions(routeID string) []RouteCondition
    GetAffectedRoutes(segmentID string) []string
    ExpireConditions() int
    UpdateRouteProgress(routeID string, currentSegment int) error
    ConditionStats() ConditionStatistics
}
```

**Required Helper Functions**:
- `CalculateRouteETA()` - ETA computation with segment and condition factors
- `ScoreAlternative()` - Composite scoring for alternative routes
- `FindAlternativeSegments()` - Bypass option identification
- `ConditionSeverityImpact()` - Delay multiplier calculation
- `ShouldTriggerReroute()` - Decision threshold evaluation

**Acceptance Criteria**:
1. Unit tests in `tests/unit/reroute_test.go` covering route registration, condition management, reroute evaluation, concurrent updates, affected route lookup, and ETA calculation
2. Integration with `internal/routing.Route` type for route representation
3. Use `internal/statistics` for metrics tracking
4. Service registrable in `shared/contracts/contracts.go`
5. Minimum 80% line coverage for the reroute package

---

### Task 3: Driver Performance Tracker (Greenfield Implementation)

Implement a driver performance tracking service that monitors key metrics (on-time delivery, fuel efficiency, safety scores), calculates performance ratings, and identifies drivers needing intervention or recognition.

**Package Location**: Create `internal/performance/performance.go`

**Interface Contract**:

The service must implement the following interface and types:

```go
type DriverProfile struct {
    DriverID      string
    Name          string
    LicenseClass  string
    HireDate      time.Time
    Region        string
    VehicleType   string
    BaselineScore float64
}

type DeliveryMetric struct {
    ID               string
    DriverID         string
    OrderID          string
    ScheduledArrival time.Time
    ActualArrival    time.Time
    DistanceKm       float64
    FuelUsedLiters   float64
    IdleTimeMinutes  int
    HardBrakeCount   int
    SpeedingEvents   int
    CustomerRating   float64
    CompletedAt      time.Time
}

type PerformanceScore struct {
    DriverID          string
    Period            string  // "daily", "weekly", "monthly"
    PeriodStart       time.Time
    PeriodEnd         time.Time
    OnTimeScore       float64
    EfficiencyScore   float64
    SafetyScore       float64
    CustomerScore     float64
    OverallScore      float64
    TotalDeliveries   int
    OnTimeDeliveries  int
    LateDeliveries    int
    AvgFuelEfficiency float64
    TotalIdleMinutes  int
    TotalSafetyEvents int
    AvgCustomerRating float64
    ScoreTrend        TrendDirection
    TrendMagnitude    float64
}

type TrendDirection string // "improving", "stable", "declining"

type PerformanceAlert struct {
    ID              string
    DriverID        string
    AlertType       AlertType  // "on_time", "fuel_efficiency", "safety", "customer_rating", "improvement"
    Severity        int        // 1-3
    Message         string
    MetricValue     float64
    Threshold       float64
    CreatedAt       time.Time
    Acknowledged    bool
}

type Leaderboard struct {
    Period    string
    Region    string
    Rankings  []LeaderboardEntry
    UpdatedAt time.Time
}

type LeaderboardEntry struct {
    Rank       int
    DriverID   string
    DriverName string
    Score      float64
    Deliveries int
    Change     int
}

type ScoringWeights struct {
    OnTime     float64
    Efficiency float64
    Safety     float64
    Customer   float64
}

type DriverStatistics struct {
    TotalDrivers         int
    ActiveDrivers        int
    AvgOverallScore      float64
    AvgOnTimeRate        float64
    AvgFuelEfficiency    float64
    TotalDeliveries      int
    TotalAlerts          int
    UnacknowledgedAlerts int
}

type DriverPerformanceService interface {
    RegisterDriver(profile DriverProfile) error
    UpdateDriver(driverID string, updates map[string]interface{}) error
    RecordDelivery(metric DeliveryMetric) error
    CalculateScore(driverID string, period string, endDate time.Time) (*PerformanceScore, error)
    GetScoreHistory(driverID string, period string, count int) []PerformanceScore
    GenerateAlerts(driverID string) []PerformanceAlert
    GetActiveAlerts(driverID string) []PerformanceAlert
    AcknowledgeAlert(alertID string, acknowledgedBy string) error
    GetLeaderboard(region string, period string, topN int) Leaderboard
    GetDriverMetrics(driverID string, start, end time.Time) []DeliveryMetric
    SetScoringWeights(onTime, efficiency, safety, customer float64) error
    GetScoringWeights() ScoringWeights
    DriverStats() DriverStatistics
}
```

**Required Helper Functions**:
- `CalculateOnTimeScore()` - Convert on-time rate to 0-100 score
- `CalculateEfficiencyScore()` - Convert fuel efficiency to score based on baseline
- `CalculateSafetyScore()` - Convert safety events to score
- `CalculateCustomerScore()` - Convert average rating to score
- `DetermineTrend()` - Analyze score history for trend direction
- `ShouldAlert()` - Check if metric violates threshold
- `GenerateAlertMessage()` - Create human-readable alert text

**Acceptance Criteria**:
1. Unit tests in `tests/unit/performance_test.go` covering driver registration, metric recording, score calculation, composite scoring, trend detection, alert generation, leaderboard ranking, concurrent recording, and edge cases
2. Integration with `pkg/models.DispatchOrder` for order references
3. Use `internal/statistics` for statistical calculations
4. Service registrable in `shared/contracts/contracts.go`
5. Minimum 80% line coverage for the performance package

---

## Service Registration

Add new services to `shared/contracts/contracts.go`:

```go
"delivery":    {ID: "delivery", Port: 8138, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"security"}},
"reroute":     {ID: "reroute", Port: 8139, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"routing"}},
"performance": {ID: "performance", Port: 8140, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"analytics"}},
```

## Code Style Guidelines

Follow existing patterns in the codebase:
- Use `sync.Mutex` or `sync.RWMutex` for thread-safe data structures
- Implement constructor functions (e.g., `NewServiceName()`)
- Include validation functions for input data
- Use descriptive error messages with context
- Document exported types and functions with comments

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
