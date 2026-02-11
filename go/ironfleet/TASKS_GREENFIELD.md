# IronFleet Greenfield Tasks

These tasks require implementing NEW modules from scratch following IronFleet's existing architectural patterns. Each task builds on the fleet management platform's routing, security, and resilience capabilities.

---

## Task 1: Fuel Consumption Optimizer

### Overview

Implement a fuel consumption optimization service that analyzes route segments, vessel characteristics, and environmental conditions to compute fuel-efficient routes and predict consumption patterns across the fleet.

### Module Location

Create the following files:
- `internal/fuel/fuel.go` - Core fuel calculation logic
- `services/fuel/service.go` - Service layer for fleet-wide fuel analytics

### Interface Contract

```go
// internal/fuel/fuel.go
package fuel

import (
    "sync"
    "time"
)

// ConsumptionRate represents fuel consumption parameters for a vessel class.
type ConsumptionRate struct {
    VesselClass     string  // e.g., "tanker", "container", "bulk"
    BaseRateLPerKm  float64 // liters per kilometer at cruising speed
    SpeedFactor     float64 // multiplier per knot above optimal speed
    LoadFactor      float64 // additional consumption per ton of cargo
}

// RouteSegment represents a portion of a route with environmental conditions.
type RouteSegment struct {
    SegmentID      string
    From           string
    To             string
    DistanceKm     float64
    CurrentKnots   float64 // ocean current speed (positive = favorable)
    WindKnots      float64 // headwind (positive = opposing)
    WaveHeightM    float64 // significant wave height
}

// FuelEstimate contains the predicted fuel consumption for a route.
type FuelEstimate struct {
    TotalLiters     float64
    SegmentBreakdown map[string]float64 // segment ID -> liters
    EfficiencyScore float64             // 0.0 to 1.0, higher is better
    OptimalSpeed    float64             // recommended cruising speed in knots
}

// FuelOptimizer provides fuel consumption calculations and route optimization.
// Thread-safe for concurrent access.
type FuelOptimizer interface {
    // RegisterRate adds or updates a consumption rate profile for a vessel class.
    // Returns error if vessel class is empty or rates are non-positive.
    RegisterRate(rate ConsumptionRate) error

    // EstimateConsumption calculates fuel needs for a route.
    // Takes into account vessel class, cargo load, desired speed, and conditions.
    // Returns error if vessel class is unknown or segments are empty.
    EstimateConsumption(vesselClass string, cargoTons float64, speedKnots float64, segments []RouteSegment) (FuelEstimate, error)

    // ComputeOptimalSpeed finds the most fuel-efficient speed for given conditions.
    // Balances fuel consumption against arrival time requirements.
    // Returns error if maxArrivalHours is not achievable at any speed.
    ComputeOptimalSpeed(vesselClass string, cargoTons float64, segments []RouteSegment, maxArrivalHours float64) (float64, error)

    // CompareRoutes evaluates multiple route options and ranks by fuel efficiency.
    // Returns routes sorted by efficiency score (best first).
    CompareRoutes(vesselClass string, cargoTons float64, speedKnots float64, routeOptions [][]RouteSegment) ([]FuelEstimate, error)
}

// FuelAuditLog tracks fuel consumption predictions vs actuals for model calibration.
type FuelAuditLog struct {
    mu      sync.Mutex
    entries []FuelAuditEntry
}

type FuelAuditEntry struct {
    VoyageID         string
    EstimatedLiters  float64
    ActualLiters     float64
    Variance         float64 // (actual - estimated) / estimated
    RecordedAt       time.Time
}

// NewFuelAuditLog creates a new audit log for fuel predictions.
func NewFuelAuditLog() *FuelAuditLog

// Record adds a completed voyage's fuel data for model improvement.
// Returns error if voyageID is empty or liters are negative.
func (l *FuelAuditLog) Record(voyageID string, estimated, actual float64) error

// VarianceReport returns entries where variance exceeds the given threshold.
// Useful for identifying routes or conditions where the model underperforms.
func (l *FuelAuditLog) VarianceReport(threshold float64) []FuelAuditEntry

// AverageVariance computes mean absolute variance across all entries.
// Returns 0.0 if no entries exist.
func (l *FuelAuditLog) AverageVariance() float64
```

```go
// services/fuel/service.go
package fuel

var Service = map[string]string{"name": "fuel", "status": "active", "version": "1.0.0"}

// FleetFuelAnalytics provides aggregated fuel metrics across the fleet.
type FleetFuelAnalytics interface {
    // ComputeFleetEfficiency returns weighted average efficiency across active vessels.
    // Weight is proportional to cargo tonnage.
    ComputeFleetEfficiency(vessels []VesselFuelStatus) float64

    // IdentifyWastage finds vessels consuming more than expected threshold.
    // Returns vessel IDs where (actual / estimated) > wasteThreshold.
    IdentifyWastage(vessels []VesselFuelStatus, wasteThreshold float64) []string

    // ProjectMonthlyConsumption estimates total fleet fuel for upcoming month.
    // Uses historical patterns and scheduled voyages.
    ProjectMonthlyConsumption(historicalAvgDaily float64, scheduledVoyages int) float64
}

type VesselFuelStatus struct {
    VesselID        string
    CargoTons       float64
    EstimatedLiters float64
    ActualLiters    float64
    EfficiencyScore float64
}
```

### Required Types Summary

| Type | Location | Purpose |
|------|----------|---------|
| `ConsumptionRate` | internal/fuel | Vessel class fuel parameters |
| `RouteSegment` | internal/fuel | Route portion with conditions |
| `FuelEstimate` | internal/fuel | Consumption prediction result |
| `FuelOptimizer` | internal/fuel | Main optimizer interface |
| `FuelAuditLog` | internal/fuel | Prediction vs actual tracking |
| `FuelAuditEntry` | internal/fuel | Single audit record |
| `VesselFuelStatus` | services/fuel | Fleet-level vessel fuel state |
| `FleetFuelAnalytics` | services/fuel | Fleet aggregation interface |

### Architectural Patterns to Follow

1. **Service map pattern**: Use `var Service = map[string]string{...}` in service files (see `services/routing/service.go`)
2. **Mutex protection**: Use `sync.Mutex` for thread-safe state (see `internal/allocator/allocator.go` RollingWindowScheduler)
3. **Error returns**: Return explicit errors for validation failures (see `allocator.ValidateOrder`)
4. **Nil checks**: Guard against nil/empty slices and zero values (see `analytics.AverageLoad`)
5. **Section separators**: Use `// ---------------------------------------------------------------------------` for visual grouping

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/fuel_test.go` with at least 8 test functions covering:
   - Rate registration with valid/invalid inputs
   - Consumption estimation with varying conditions
   - Optimal speed calculation edge cases
   - Route comparison ranking
   - Audit log variance calculations

2. **Integration Points**:
   - Import and use `services/routing.Leg` for route distance data
   - Reference `pkg/models.VesselManifest` for cargo tonnage

3. **Test Command**:
   ```bash
   go test -v ./...
   ```

4. **Coverage**: Aim for >80% coverage on new modules

---

## Task 2: Maintenance Scheduler

### Overview

Implement a predictive maintenance scheduling system that tracks vessel component health, schedules preventive maintenance windows, and coordinates with dispatch to minimize operational disruption.

### Module Location

Create the following files:
- `internal/maintenance/maintenance.go` - Core scheduling and prediction logic
- `services/maintenance/service.go` - Service layer for fleet maintenance coordination

### Interface Contract

```go
// internal/maintenance/maintenance.go
package maintenance

import (
    "sync"
    "time"
)

// ComponentType identifies major vessel systems requiring maintenance.
type ComponentType string

const (
    ComponentEngine     ComponentType = "engine"
    ComponentPropulsion ComponentType = "propulsion"
    ComponentNavigation ComponentType = "navigation"
    ComponentHull       ComponentType = "hull"
    ComponentSafety     ComponentType = "safety"
)

// ComponentHealth represents the current state of a vessel component.
type ComponentHealth struct {
    VesselID      string
    Component     ComponentType
    HealthScore   float64   // 0.0 (failed) to 1.0 (perfect)
    OperatingHours int64    // hours since last maintenance
    LastInspection time.Time
    AlertThreshold float64  // score below which alerts are raised
}

// MaintenanceWindow represents a scheduled maintenance slot.
type MaintenanceWindow struct {
    WindowID      string
    VesselID      string
    Component     ComponentType
    ScheduledAt   time.Time
    DurationHours int
    Priority      int       // 1=critical, 2=high, 3=normal, 4=low
    Status        string    // "scheduled", "in_progress", "completed", "cancelled"
}

// MaintenanceConflict describes overlapping or problematic schedules.
type MaintenanceConflict struct {
    WindowA      string
    WindowB      string
    Reason       string    // "overlap", "insufficient_gap", "resource_contention"
    SuggestedFix string
}

// MaintenanceScheduler manages predictive maintenance scheduling.
// Thread-safe for concurrent access.
type MaintenanceScheduler interface {
    // RegisterComponent adds a component to be tracked for maintenance.
    // Returns error if vesselID or component is invalid.
    RegisterComponent(health ComponentHealth) error

    // UpdateHealth records new health readings for a component.
    // Returns true if health dropped below alert threshold.
    UpdateHealth(vesselID string, component ComponentType, newScore float64, operatingHours int64) (alert bool, err error)

    // PredictFailure estimates time until component needs maintenance.
    // Uses linear degradation model based on operating hours and current health.
    // Returns hours until predicted failure (health < 0.2).
    PredictFailure(vesselID string, component ComponentType) (hoursRemaining float64, err error)

    // ScheduleMaintenance creates a maintenance window.
    // Returns error if window conflicts with existing schedule or vessel is in transit.
    ScheduleMaintenance(window MaintenanceWindow) error

    // FindOptimalWindow suggests best maintenance time considering:
    // - Vessel dispatch schedule (from allocator)
    // - Port availability
    // - Component priority
    // Returns earliest available window that minimizes disruption.
    FindOptimalWindow(vesselID string, component ComponentType, durationHours int, priority int, notBefore time.Time) (MaintenanceWindow, error)

    // DetectConflicts checks all scheduled windows for problems.
    // Returns list of conflicts that need resolution.
    DetectConflicts() []MaintenanceConflict

    // GetOverdueComponents returns components past their recommended maintenance interval.
    // Interval is based on component type (engine=5000hrs, hull=10000hrs, etc.)
    GetOverdueComponents() []ComponentHealth
}

// MaintenanceHistory tracks completed maintenance for trend analysis.
type MaintenanceHistory struct {
    mu       sync.Mutex
    records  []MaintenanceRecord
}

type MaintenanceRecord struct {
    VesselID       string
    Component      ComponentType
    CompletedAt    time.Time
    ActualDuration int           // hours
    CostUSD        float64
    FindingsNotes  string
}

// NewMaintenanceHistory creates a new history tracker.
func NewMaintenanceHistory() *MaintenanceHistory

// Record adds a completed maintenance event.
func (h *MaintenanceHistory) Record(record MaintenanceRecord) error

// AverageDuration returns mean maintenance duration for a component type.
// Useful for scheduling accuracy.
func (h *MaintenanceHistory) AverageDuration(component ComponentType) float64

// TotalCost returns sum of maintenance costs in date range.
func (h *MaintenanceHistory) TotalCost(from, to time.Time) float64

// FrequencyByVessel returns count of maintenance events per vessel.
// Identifies vessels requiring excessive maintenance.
func (h *MaintenanceHistory) FrequencyByVessel() map[string]int
```

```go
// services/maintenance/service.go
package maintenance

var Service = map[string]string{"name": "maintenance", "status": "active", "version": "1.0.0"}

// FleetMaintenanceCoordinator provides fleet-wide maintenance oversight.
type FleetMaintenanceCoordinator interface {
    // ComputeFleetReadiness returns percentage of vessels with all components healthy.
    // Healthy means all component scores > 0.5.
    ComputeFleetReadiness(vessels []VesselMaintenanceStatus) float64

    // PrioritizeMaintenanceQueue orders pending maintenance by urgency.
    // Considers: component criticality, health score, time since last service.
    // Returns vessel IDs in priority order (most urgent first).
    PrioritizeMaintenanceQueue(pending []MaintenanceWindow) []string

    // EstimateDowntime projects total fleet maintenance hours for period.
    EstimateDowntime(from, to time.Time) float64

    // GenerateMaintenanceReport creates summary for operations team.
    GenerateMaintenanceReport(periodDays int) MaintenanceReport
}

type VesselMaintenanceStatus struct {
    VesselID          string
    ComponentHealths  map[ComponentType]float64
    LastMaintenanceAt time.Time
    NextScheduledAt   time.Time
}

type MaintenanceReport struct {
    TotalVessels      int
    VesselsHealthy    int
    VesselsCritical   int
    ScheduledWindows  int
    CompletedThisPeriod int
    TotalCostUSD      float64
    TopIssueComponent ComponentType
}
```

### Required Types Summary

| Type | Location | Purpose |
|------|----------|---------|
| `ComponentType` | internal/maintenance | Enum for vessel systems |
| `ComponentHealth` | internal/maintenance | Component state tracking |
| `MaintenanceWindow` | internal/maintenance | Scheduled maintenance slot |
| `MaintenanceConflict` | internal/maintenance | Schedule problem descriptor |
| `MaintenanceScheduler` | internal/maintenance | Main scheduler interface |
| `MaintenanceHistory` | internal/maintenance | Completed maintenance log |
| `MaintenanceRecord` | internal/maintenance | Single maintenance event |
| `VesselMaintenanceStatus` | services/maintenance | Fleet-level vessel state |
| `MaintenanceReport` | services/maintenance | Operations summary |
| `FleetMaintenanceCoordinator` | services/maintenance | Fleet coordination interface |

### Architectural Patterns to Follow

1. **Constant definitions**: Use `const` blocks for enum-like values (see `internal/resilience/replay.go` states)
2. **Manager pattern**: Use `*Manager` structs with `New*Manager()` constructors (see `CheckpointManager`)
3. **History tracking**: Store timestamped records for trend analysis (see `PolicyChange`)
4. **Priority ordering**: Use descending priority sorts (see `allocator.PlanDispatch`)
5. **Validation errors**: Return descriptive `fmt.Errorf()` messages (see `models.ValidateDispatchOrder`)

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/maintenance_test.go` with at least 10 test functions covering:
   - Component registration and health updates
   - Failure prediction accuracy
   - Window scheduling with conflicts
   - Optimal window finding
   - History statistics

2. **Integration Points**:
   - Reference `internal/allocator.Order` for dispatch schedule awareness
   - Use `pkg/models.VesselManifest` for vessel identification
   - Integrate with `services/notifications` for maintenance alerts

3. **Test Command**:
   ```bash
   go test -v ./...
   ```

4. **Coverage**: Aim for >80% coverage on new modules

---

## Task 3: Geofence Alert Service

### Overview

Implement a geofence monitoring service that tracks vessel positions against defined geographic zones, triggers alerts for boundary violations, and enforces operational restrictions based on zone policies.

### Module Location

Create the following files:
- `internal/geofence/geofence.go` - Core geofence geometry and violation detection
- `services/geofence/service.go` - Service layer for fleet geofence monitoring

### Interface Contract

```go
// internal/geofence/geofence.go
package geofence

import (
    "sync"
    "time"
)

// ZoneType categorizes geofence zones by their purpose.
type ZoneType string

const (
    ZoneRestricted   ZoneType = "restricted"    // No entry allowed
    ZoneControlled   ZoneType = "controlled"    // Entry requires authorization
    ZoneMonitored    ZoneType = "monitored"     // Track entry/exit, no restrictions
    ZoneEmergency    ZoneType = "emergency"     // Dynamic zone for incidents
    ZonePort         ZoneType = "port"          // Port approach/departure zones
)

// Coordinate represents a geographic point.
type Coordinate struct {
    Latitude  float64 // degrees, -90 to +90
    Longitude float64 // degrees, -180 to +180
}

// Zone defines a geographic boundary with associated policy.
type Zone struct {
    ZoneID      string
    Name        string
    Type        ZoneType
    Polygon     []Coordinate  // ordered vertices defining boundary
    Centroid    Coordinate    // center point for distance calculations
    RadiusKm    float64       // if > 0, use circular zone instead of polygon
    ActiveFrom  time.Time     // zone becomes active
    ActiveUntil time.Time     // zone deactivates (zero = permanent)
    Metadata    map[string]string
}

// VesselPosition represents a vessel's current location.
type VesselPosition struct {
    VesselID   string
    Position   Coordinate
    Heading    float64    // degrees, 0-360
    SpeedKnots float64
    Timestamp  time.Time
}

// ViolationSeverity indicates how serious a geofence breach is.
type ViolationSeverity int

const (
    SeverityInfo     ViolationSeverity = 1 // Monitored zone entry
    SeverityWarning  ViolationSeverity = 2 // Approaching restricted zone
    SeverityCritical ViolationSeverity = 3 // Inside restricted zone
    SeverityEmergency ViolationSeverity = 4 // Unresponsive in emergency zone
)

// Violation records a geofence breach event.
type Violation struct {
    ViolationID  string
    VesselID     string
    ZoneID       string
    Severity     ViolationSeverity
    EntryTime    time.Time
    ExitTime     time.Time         // zero if still inside
    EntryPoint   Coordinate
    MaxPenetrationKm float64       // how deep into zone
    Acknowledged bool
}

// GeofenceEngine provides zone management and violation detection.
// Thread-safe for concurrent access.
type GeofenceEngine interface {
    // RegisterZone adds a new geofence zone.
    // Returns error if zone ID exists or polygon has < 3 vertices.
    RegisterZone(zone Zone) error

    // UpdateZone modifies an existing zone.
    // Returns error if zone not found.
    UpdateZone(zone Zone) error

    // DeactivateZone marks a zone as inactive without deleting.
    DeactivateZone(zoneID string) error

    // CheckPosition evaluates a vessel position against all active zones.
    // Returns list of violations (may be empty if no breaches).
    CheckPosition(pos VesselPosition) []Violation

    // IsInsideZone tests if a coordinate is within a specific zone.
    IsInsideZone(coord Coordinate, zoneID string) (bool, error)

    // FindNearbyZones returns zones within given distance of coordinate.
    // Useful for proximity warnings.
    FindNearbyZones(coord Coordinate, radiusKm float64) []Zone

    // GetActiveViolations returns all unresolved violations.
    GetActiveViolations() []Violation

    // AcknowledgeViolation marks a violation as reviewed by operator.
    AcknowledgeViolation(violationID string, operatorID string) error

    // ProjectedViolation predicts if vessel will enter zone given current heading/speed.
    // Returns time until entry and distance to boundary.
    ProjectedViolation(pos VesselPosition, zoneID string) (timeToEntry time.Duration, distanceKm float64, willViolate bool, err error)
}

// GeofenceTracker maintains real-time vessel positions and zone states.
type GeofenceTracker struct {
    mu             sync.RWMutex
    positions      map[string]VesselPosition // vesselID -> latest position
    zoneOccupants  map[string][]string       // zoneID -> vessel IDs currently inside
    violationLog   []Violation
}

// NewGeofenceTracker creates a new position tracker.
func NewGeofenceTracker() *GeofenceTracker

// UpdatePosition records a new vessel position and returns any new violations.
func (t *GeofenceTracker) UpdatePosition(pos VesselPosition, engine GeofenceEngine) []Violation

// GetVesselsInZone returns all vessel IDs currently inside a zone.
func (t *GeofenceTracker) GetVesselsInZone(zoneID string) []string

// VesselZones returns all zone IDs a vessel is currently inside.
func (t *GeofenceTracker) VesselZones(vesselID string) []string

// ViolationCount returns total violations in time range.
func (t *GeofenceTracker) ViolationCount(from, to time.Time) int
```

```go
// services/geofence/service.go
package geofence

var Service = map[string]string{"name": "geofence", "status": "active", "version": "1.0.0"}

// FleetGeofenceMonitor provides fleet-wide geofence oversight.
type FleetGeofenceMonitor interface {
    // ComputeComplianceRate returns percentage of vessels with no active violations.
    ComputeComplianceRate(vessels []VesselGeofenceStatus) float64

    // GetHighRiskVessels returns vessels with repeated or severe violations.
    // Threshold is minimum violation count to be considered high risk.
    GetHighRiskVessels(threshold int) []string

    // GenerateHeatmap returns violation frequency by zone for the period.
    // Useful for identifying problematic areas.
    GenerateHeatmap(from, to time.Time) map[string]int

    // EstimateRiskScore computes aggregate risk for a route.
    // Considers zone types along path and historical violation rates.
    EstimateRiskScore(routeWaypoints []Coordinate) float64

    // BroadcastAlert sends geofence alerts to appropriate services.
    // Integrates with notifications service for escalation.
    BroadcastAlert(violation Violation) error
}

type VesselGeofenceStatus struct {
    VesselID          string
    CurrentPosition   Coordinate
    ActiveViolations  int
    TotalViolations   int
    LastViolationAt   time.Time
    ComplianceScore   float64 // 0.0 to 1.0, based on recent history
}

// ZoneSummary provides aggregate statistics for a zone.
type ZoneSummary struct {
    ZoneID             string
    Name               string
    Type               ZoneType
    CurrentOccupants   int
    TotalEntries       int
    TotalViolations    int
    AverageDwellHours  float64
}
```

### Required Types Summary

| Type | Location | Purpose |
|------|----------|---------|
| `ZoneType` | internal/geofence | Enum for zone categories |
| `Coordinate` | internal/geofence | Geographic point |
| `Zone` | internal/geofence | Geofence boundary definition |
| `VesselPosition` | internal/geofence | Vessel location snapshot |
| `ViolationSeverity` | internal/geofence | Breach severity level |
| `Violation` | internal/geofence | Geofence breach record |
| `GeofenceEngine` | internal/geofence | Main detection interface |
| `GeofenceTracker` | internal/geofence | Real-time position tracking |
| `VesselGeofenceStatus` | services/geofence | Fleet-level vessel state |
| `ZoneSummary` | services/geofence | Zone statistics |
| `FleetGeofenceMonitor` | services/geofence | Fleet monitoring interface |

### Architectural Patterns to Follow

1. **RWMutex for read-heavy**: Use `sync.RWMutex` when reads outnumber writes (position lookups)
2. **Map-based lookups**: Use maps for O(1) vessel/zone lookups (see `contracts.ServiceDefs`)
3. **Severity constants**: Use typed constants for severity levels (see `models.Severity*`)
4. **Zero value handling**: Return meaningful defaults for missing data (see `statistics.MovingAverage`)
5. **Timestamp tracking**: Include `time.Time` fields for temporal analysis

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/geofence_test.go` with at least 12 test functions covering:
   - Zone registration with polygons and circles
   - Point-in-polygon detection
   - Haversine distance calculations
   - Violation detection and severity assignment
   - Projected violation predictions
   - Tracker position updates

2. **Integration Points**:
   - Use `services/security` for authorization checks on controlled zones
   - Integrate with `services/notifications` for alert broadcasting
   - Reference `services/routing.Leg` for route waypoint data

3. **Geometry Requirements**:
   - Implement point-in-polygon using ray casting algorithm
   - Implement Haversine formula for distance calculations
   - Handle international date line crossing for longitude

4. **Test Command**:
   ```bash
   go test -v ./...
   ```

5. **Coverage**: Aim for >80% coverage on new modules

---

## General Guidelines

### Code Organization

```
go/ironfleet/
├── internal/
│   ├── fuel/
│   │   └── fuel.go
│   ├── maintenance/
│   │   └── maintenance.go
│   └── geofence/
│       └── geofence.go
├── services/
│   ├── fuel/
│   │   └── service.go
│   ├── maintenance/
│   │   └── service.go
│   └── geofence/
│       └── service.go
└── tests/
    └── unit/
        ├── fuel_test.go
        ├── maintenance_test.go
        └── geofence_test.go
```

### Shared Contract Updates

After implementing new services, update `shared/contracts/contracts.go`:

```go
// Add to ServiceDefs map
"fuel":        {ID: "fuel", Port: 8138, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"routing"}},
"maintenance": {ID: "maintenance", Port: 8139, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"allocator", "notifications"}},
"geofence":    {ID: "geofence", Port: 8140, HealthPath: "/health", Version: "1.0.0", Dependencies: []string{"security", "notifications"}},
```

### Testing Best Practices

1. **Table-driven tests**: Use `[]struct{name string; input X; want Y}` pattern
2. **Subtests**: Use `t.Run(name, func(t *testing.T){...})` for organization
3. **Concurrency tests**: Test mutex-protected operations under concurrent access
4. **Edge cases**: Test empty inputs, zero values, negative numbers, boundary conditions
5. **Error paths**: Verify error returns for invalid inputs

### Run All Tests

```bash
go test -v ./...
```
