# AtlasDispatch Greenfield Tasks

These tasks require implementing **new modules from scratch** that integrate with the existing AtlasDispatch dispatch and routing platform. Each task defines interfaces, required types, and acceptance criteria.

**Test Command:** `go test -v ./...`

---

## Task 1: Proof of Delivery Service

### Overview

Implement a proof of delivery (POD) service that captures delivery confirmations, signatures, photos, and timestamps. This service integrates with the workflow engine to transition orders to "completed" state upon successful delivery confirmation.

### Package Location

Create: `internal/delivery/delivery.go`

### Interface Contract

```go
package delivery

import (
    "time"
)

// DeliveryProof represents a proof of delivery record
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

// Location represents GPS coordinates for delivery confirmation
type Location struct {
    Lat       float64
    Lng       float64
    Accuracy  float64 // meters
    Timestamp time.Time
}

// ProofStatus represents the validation state of a proof
type ProofStatus string

const (
    ProofPending   ProofStatus = "pending"
    ProofValidated ProofStatus = "validated"
    ProofRejected  ProofStatus = "rejected"
    ProofExpired   ProofStatus = "expired"
)

// ValidationResult contains the outcome of proof validation
type ValidationResult struct {
    Valid           bool
    Reason          string
    LocationMatch   bool
    TimestampValid  bool
    SignatureValid  bool
}

// DeliveryProofService manages proof of delivery records
type DeliveryProofService interface {
    // SubmitProof records a new proof of delivery for an order.
    // Returns error if order doesn't exist or proof already submitted.
    SubmitProof(proof DeliveryProof) error

    // ValidateProof checks if a proof meets all requirements:
    // - Location within acceptable radius of destination
    // - Timestamp within delivery window
    // - Signature hash is non-empty and valid format
    ValidateProof(proofID string, destLat, destLng float64, maxRadiusM float64, windowMinutes int) ValidationResult

    // GetProof retrieves a proof by ID
    GetProof(proofID string) *DeliveryProof

    // GetProofByOrder retrieves proof for a specific order
    GetProofByOrder(orderID string) *DeliveryProof

    // ListPendingProofs returns all proofs awaiting validation
    ListPendingProofs() []DeliveryProof

    // ExpireStaleProofs marks proofs older than maxAge as expired
    // Returns count of expired proofs
    ExpireStaleProofs(maxAge time.Duration) int

    // UpdateStatus changes the status of a proof
    UpdateStatus(proofID string, status ProofStatus, reason string) error

    // ProofStats returns aggregate statistics
    ProofStats() ProofStatistics
}

// ProofStatistics contains aggregate proof metrics
type ProofStatistics struct {
    TotalProofs     int
    PendingCount    int
    ValidatedCount  int
    RejectedCount   int
    ExpiredCount    int
    AvgValidationMs float64
}
```

### Required Helper Functions

```go
// CalculateDistance returns distance in meters between two coordinates
// using the Haversine formula
func CalculateDistance(lat1, lng1, lat2, lng2 float64) float64

// ValidateSignatureHash checks if a signature hash is valid SHA256 hex format
func ValidateSignatureHash(hash string) bool

// IsWithinTimeWindow checks if a timestamp is within minutes of reference time
func IsWithinTimeWindow(timestamp, reference time.Time, windowMinutes int) bool

// GenerateProofID creates a unique proof ID from order ID and timestamp
func GenerateProofID(orderID string, timestamp time.Time) string
```

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/delivery_test.go`):
   - Test proof submission with valid/invalid data
   - Test location distance calculation (edge cases: same point, antipodal points, equator crossing)
   - Test time window validation (before, within, after window)
   - Test signature hash validation
   - Test concurrent proof submissions (thread safety)
   - Test stale proof expiration
   - Test statistics accuracy

2. **Integration Points**:
   - Proof validation should use `security.Digest()` for hash verification
   - Service should be registrable in `shared/contracts/contracts.go`
   - Status changes should be loggable for audit trail

3. **Coverage**: Minimum 80% line coverage for the delivery package

---

## Task 2: Dynamic Rerouting Engine

### Overview

Implement a dynamic rerouting engine that recomputes optimal routes when conditions change (traffic, weather, vehicle breakdowns). The engine should maintain route state, detect when rerouting is beneficial, and integrate with the existing routing module.

### Package Location

Create: `internal/reroute/reroute.go`

### Interface Contract

```go
package reroute

import (
    "time"
)

// RouteCondition represents current conditions affecting a route segment
type RouteCondition struct {
    SegmentID     string
    ConditionType ConditionType
    Severity      int       // 1-5, where 5 is most severe
    DelayMinutes  int       // estimated additional delay
    ReportedAt    time.Time
    ExpiresAt     time.Time
    Source        string    // "traffic", "weather", "incident", "manual"
}

// ConditionType categorizes route disruptions
type ConditionType string

const (
    ConditionTraffic   ConditionType = "traffic"
    ConditionWeather   ConditionType = "weather"
    ConditionIncident  ConditionType = "incident"
    ConditionClosure   ConditionType = "closure"
    ConditionHazmat    ConditionType = "hazmat"
)

// RerouteDecision contains the engine's recommendation
type RerouteDecision struct {
    ShouldReroute     bool
    OriginalETA       time.Time
    NewETA            time.Time
    TimeSavedMinutes  int
    CostDelta         float64   // positive = more expensive, negative = cheaper
    AffectedSegments  []string
    AlternativeRoute  []RouteSegment
    Confidence        float64   // 0.0-1.0 confidence in recommendation
    Reason            string
}

// RouteSegment represents a portion of a route
type RouteSegment struct {
    ID            string
    FromLocation  string
    ToLocation    string
    DistanceKm    float64
    BaseTimeMin   int
    CurrentTimeMin int  // adjusted for conditions
}

// ActiveRoute represents a route currently being executed
type ActiveRoute struct {
    ID              string
    OrderID         string
    Segments        []RouteSegment
    CurrentSegment  int
    StartedAt       time.Time
    EstimatedArrival time.Time
    LastUpdated     time.Time
}

// RerouteEngine manages dynamic route optimization
type RerouteEngine interface {
    // RegisterRoute adds an active route for monitoring
    RegisterRoute(route ActiveRoute) error

    // UnregisterRoute removes a route from monitoring
    UnregisterRoute(routeID string) error

    // ReportCondition adds or updates a route condition
    ReportCondition(condition RouteCondition) error

    // ClearCondition removes a condition from a segment
    ClearCondition(segmentID string, conditionType ConditionType) error

    // EvaluateReroute analyzes if a route should be changed
    // minTimeSavings: minimum minutes saved to recommend reroute
    // maxCostIncrease: maximum acceptable cost increase percentage
    EvaluateReroute(routeID string, minTimeSavings int, maxCostIncrease float64) RerouteDecision

    // GetActiveConditions returns all conditions affecting a route
    GetActiveConditions(routeID string) []RouteCondition

    // GetAffectedRoutes returns all routes impacted by a segment condition
    GetAffectedRoutes(segmentID string) []string

    // ExpireConditions removes conditions past their expiry time
    // Returns count of expired conditions
    ExpireConditions() int

    // UpdateRouteProgress updates current segment for an active route
    UpdateRouteProgress(routeID string, currentSegment int) error

    // ConditionStats returns aggregate condition statistics
    ConditionStats() ConditionStatistics
}

// ConditionStatistics contains aggregate metrics
type ConditionStatistics struct {
    ActiveConditions   int
    ConditionsByType   map[ConditionType]int
    AvgSeverity        float64
    TotalDelayMinutes  int
    AffectedRoutes     int
}
```

### Required Helper Functions

```go
// CalculateRouteETA computes estimated arrival based on segments and conditions
func CalculateRouteETA(segments []RouteSegment, startTime time.Time, conditions map[string][]RouteCondition) time.Time

// ScoreAlternative calculates a composite score for an alternative route
// considering time, cost, and reliability factors
func ScoreAlternative(original, alternative []RouteSegment, conditions map[string][]RouteCondition) float64

// FindAlternativeSegments identifies bypass options for a blocked segment
func FindAlternativeSegments(blockedSegmentID string, adjacencyMap map[string][]string) [][]RouteSegment

// ConditionSeverityImpact returns delay multiplier for a severity level
func ConditionSeverityImpact(severity int) float64

// ShouldTriggerReroute determines if conditions warrant evaluation
// based on cumulative delay and severity thresholds
func ShouldTriggerReroute(conditions []RouteCondition, delayThreshold int, severityThreshold int) bool
```

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/reroute_test.go`):
   - Test route registration/unregistration
   - Test condition reporting and expiration
   - Test reroute evaluation with various scenarios
   - Test concurrent condition updates (thread safety)
   - Test affected route lookup
   - Test ETA calculation accuracy

2. **Integration Points**:
   - Should integrate with `internal/routing.Route` type for route representation
   - Should use `internal/statistics` for metrics tracking
   - Service should be registrable in `shared/contracts/contracts.go`

3. **Coverage**: Minimum 80% line coverage for the reroute package

---

## Task 3: Driver Performance Tracker

### Overview

Implement a driver performance tracking service that monitors key metrics (on-time delivery, fuel efficiency, safety scores), calculates performance ratings, and identifies drivers needing intervention or recognition.

### Package Location

Create: `internal/performance/performance.go`

### Interface Contract

```go
package performance

import (
    "time"
)

// DriverProfile contains driver identification and baseline metrics
type DriverProfile struct {
    DriverID      string
    Name          string
    LicenseClass  string
    HireDate      time.Time
    Region        string
    VehicleType   string
    BaselineScore float64 // established performance baseline
}

// DeliveryMetric records a single delivery's performance data
type DeliveryMetric struct {
    ID                string
    DriverID          string
    OrderID           string
    ScheduledArrival  time.Time
    ActualArrival     time.Time
    DistanceKm        float64
    FuelUsedLiters    float64
    IdleTimeMinutes   int
    HardBrakeCount    int
    SpeedingEvents    int
    CustomerRating    float64 // 1.0-5.0, 0 if not rated
    CompletedAt       time.Time
}

// PerformanceScore represents calculated driver performance
type PerformanceScore struct {
    DriverID          string
    Period            string    // "daily", "weekly", "monthly"
    PeriodStart       time.Time
    PeriodEnd         time.Time

    // Component scores (0-100)
    OnTimeScore       float64
    EfficiencyScore   float64
    SafetyScore       float64
    CustomerScore     float64

    // Composite score (weighted average)
    OverallScore      float64

    // Raw metrics
    TotalDeliveries   int
    OnTimeDeliveries  int
    LateDeliveries    int
    AvgFuelEfficiency float64 // km per liter
    TotalIdleMinutes  int
    TotalSafetyEvents int
    AvgCustomerRating float64

    // Trend indicators
    ScoreTrend        TrendDirection
    TrendMagnitude    float64 // percentage change from prior period
}

// TrendDirection indicates performance trajectory
type TrendDirection string

const (
    TrendImproving TrendDirection = "improving"
    TrendStable    TrendDirection = "stable"
    TrendDeclining TrendDirection = "declining"
)

// PerformanceAlert represents a flagged performance issue
type PerformanceAlert struct {
    ID          string
    DriverID    string
    AlertType   AlertType
    Severity    int       // 1-3, where 3 is most severe
    Message     string
    MetricValue float64
    Threshold   float64
    CreatedAt   time.Time
    Acknowledged bool
}

// AlertType categorizes performance alerts
type AlertType string

const (
    AlertOnTime      AlertType = "on_time"
    AlertFuel        AlertType = "fuel_efficiency"
    AlertSafety      AlertType = "safety"
    AlertCustomer    AlertType = "customer_rating"
    AlertImprovement AlertType = "improvement"  // positive alert for recognition
)

// Leaderboard represents ranked drivers for a period
type Leaderboard struct {
    Period    string
    Region    string
    Rankings  []LeaderboardEntry
    UpdatedAt time.Time
}

// LeaderboardEntry represents a driver's ranking
type LeaderboardEntry struct {
    Rank       int
    DriverID   string
    DriverName string
    Score      float64
    Deliveries int
    Change     int // position change from previous period
}

// DriverPerformanceService manages driver performance tracking
type DriverPerformanceService interface {
    // RegisterDriver adds a driver profile to the system
    RegisterDriver(profile DriverProfile) error

    // UpdateDriver modifies driver profile information
    UpdateDriver(driverID string, updates map[string]interface{}) error

    // RecordDelivery adds a delivery metric for a driver
    RecordDelivery(metric DeliveryMetric) error

    // CalculateScore computes performance score for a driver and period
    // Period options: "daily", "weekly", "monthly"
    CalculateScore(driverID string, period string, endDate time.Time) (*PerformanceScore, error)

    // GetScoreHistory retrieves historical scores for trending
    GetScoreHistory(driverID string, period string, count int) []PerformanceScore

    // GenerateAlerts evaluates metrics and creates alerts for threshold violations
    // Returns newly generated alerts
    GenerateAlerts(driverID string) []PerformanceAlert

    // GetActiveAlerts retrieves unacknowledged alerts for a driver
    GetActiveAlerts(driverID string) []PerformanceAlert

    // AcknowledgeAlert marks an alert as reviewed
    AcknowledgeAlert(alertID string, acknowledgedBy string) error

    // GetLeaderboard returns ranked drivers for a region and period
    GetLeaderboard(region string, period string, topN int) Leaderboard

    // GetDriverMetrics retrieves raw delivery metrics for a driver in date range
    GetDriverMetrics(driverID string, start, end time.Time) []DeliveryMetric

    // SetScoringWeights configures the weights for composite score calculation
    // Weights should sum to 1.0
    SetScoringWeights(onTime, efficiency, safety, customer float64) error

    // GetScoringWeights returns current scoring configuration
    GetScoringWeights() ScoringWeights

    // DriverStats returns aggregate statistics across all drivers
    DriverStats() DriverStatistics
}

// ScoringWeights defines how component scores contribute to overall score
type ScoringWeights struct {
    OnTime     float64
    Efficiency float64
    Safety     float64
    Customer   float64
}

// DriverStatistics contains fleet-wide performance metrics
type DriverStatistics struct {
    TotalDrivers        int
    ActiveDrivers       int // drivers with deliveries in last 30 days
    AvgOverallScore     float64
    AvgOnTimeRate       float64
    AvgFuelEfficiency   float64
    TotalDeliveries     int
    TotalAlerts         int
    UnacknowledgedAlerts int
}
```

### Required Helper Functions

```go
// CalculateOnTimeScore converts on-time rate to 0-100 score
// 100% on-time = 100, with configurable penalty curve
func CalculateOnTimeScore(onTimeCount, totalCount int) float64

// CalculateEfficiencyScore converts fuel efficiency to 0-100 score
// Based on comparison to baseline for vehicle type
func CalculateEfficiencyScore(actualKmPerLiter, baselineKmPerLiter float64) float64

// CalculateSafetyScore converts safety events to 0-100 score
// Penalizes hard braking and speeding events
func CalculateSafetyScore(hardBrakes, speedingEvents, totalDeliveries int) float64

// CalculateCustomerScore converts average rating to 0-100 score
func CalculateCustomerScore(avgRating float64, ratedDeliveries, totalDeliveries int) float64

// DetermineTrend analyzes score history to identify trend direction
func DetermineTrend(scores []float64) (TrendDirection, float64)

// ShouldAlert checks if a metric value violates threshold
func ShouldAlert(metricType AlertType, value, threshold float64) bool

// GenerateAlertMessage creates human-readable alert text
func GenerateAlertMessage(alertType AlertType, driverName string, value, threshold float64) string
```

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/performance_test.go`):
   - Test driver registration and updates
   - Test delivery metric recording
   - Test score calculation for each component
   - Test composite score with various weights
   - Test trend detection (improving, stable, declining)
   - Test alert generation and acknowledgment
   - Test leaderboard ranking with ties
   - Test concurrent metric recording (thread safety)
   - Test edge cases (no deliveries, all late, perfect scores)

2. **Integration Points**:
   - Should integrate with `pkg/models.DispatchOrder` for order references
   - Should use `internal/statistics` for statistical calculations
   - Service should be registrable in `shared/contracts/contracts.go`

3. **Coverage**: Minimum 80% line coverage for the performance package

---

## General Requirements

### Code Style

Follow existing patterns observed in the codebase:
- Use `sync.Mutex` or `sync.RWMutex` for thread-safe data structures
- Implement constructor functions (e.g., `NewServiceName()`)
- Include validation functions for input data
- Use descriptive error messages with context
- Document exported types and functions with comments

### Service Registration

Add new services to `shared/contracts/contracts.go`:

```go
var ServiceDefs = map[string]ServiceDefinition{
    // ... existing services ...
    "delivery":    {ID: "delivery", Port: 8138, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"security"}},
    "reroute":     {ID: "reroute", Port: 8139, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"routing"}},
    "performance": {ID: "performance", Port: 8140, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"analytics"}},
}
```

### Error Handling

Define custom error types for each service:

```go
type ServiceError struct {
    Code    string
    Message string
    Details map[string]interface{}
}

func (e *ServiceError) Error() string {
    return fmt.Sprintf("%s: %s", e.Code, e.Message)
}
```

### Testing Pattern

Follow the existing test structure:
- Place unit tests in `tests/unit/`
- Use table-driven tests for comprehensive coverage
- Test both success and error paths
- Include concurrency tests for thread-safe components
