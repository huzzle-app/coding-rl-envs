# IncidentMesh Greenfield Tasks

These tasks require implementing **new modules from scratch** in the IncidentMesh incident management platform. Each task defines a complete interface contract, required types, and acceptance criteria. Implementations must follow existing architectural patterns found in `internal/` and `services/`.

---

## Task 1: Postmortem Generator

### Overview

Implement a **Postmortem Generator** module that analyzes resolved incidents and produces structured postmortem reports. This service aggregates incident timelines, identifies contributing factors, calculates response metrics, and generates actionable improvement recommendations.

### Location

- Internal package: `internal/postmortem/generator.go`
- Service wrapper: `services/postmortem/service.go`

### Interface Contract

```go
package postmortem

import (
    "incidentmesh/pkg/models"
    "incidentmesh/shared/contracts"
    "time"
)

// PostmortemReport represents a complete postmortem document.
type PostmortemReport struct {
    ReportID          string
    IncidentID        string
    Title             string
    Summary           string
    Timeline          []TimelineEntry
    RootCauses        []string
    ContributingFactors []string
    ImpactMetrics     ImpactMetrics
    ActionItems       []ActionItem
    GeneratedAt       time.Time
    Severity          int
    Status            string // "draft", "reviewed", "published"
}

// TimelineEntry represents a single event in the incident timeline.
type TimelineEntry struct {
    Timestamp   time.Time
    EventType   string
    Description string
    Actor       string
    Duration    time.Duration
}

// ImpactMetrics captures quantitative impact data.
type ImpactMetrics struct {
    TimeToDetect    time.Duration // Time from incident start to first alert
    TimeToRespond   time.Duration // Time from first alert to first action
    TimeToResolve   time.Duration // Total incident duration
    AffectedRegions []string
    EscalationCount int
    UnitsDispatched int
}

// ActionItem represents a follow-up task from the postmortem.
type ActionItem struct {
    ID          string
    Description string
    Owner       string
    Priority    int       // 1=critical, 2=high, 3=medium, 4=low
    DueDate     time.Time
    Status      string    // "open", "in_progress", "completed"
    Category    string    // "process", "tooling", "training", "infrastructure"
}

// Generator defines the postmortem generation interface.
type Generator interface {
    // GenerateReport creates a postmortem report from incident data and audit trail.
    // Returns error if incident is still active or if required data is missing.
    GenerateReport(incident models.Incident, events []contracts.IncidentEvent, audits []contracts.AuditEntry) (*PostmortemReport, error)

    // BuildTimeline constructs a chronological timeline from events and audit entries.
    // Events and audits are merged and sorted by timestamp.
    BuildTimeline(events []contracts.IncidentEvent, audits []contracts.AuditEntry) []TimelineEntry

    // CalculateMetrics computes impact metrics from the incident timeline.
    // Returns zero-value metrics if timeline is empty.
    CalculateMetrics(incident models.Incident, timeline []TimelineEntry) ImpactMetrics

    // IdentifyRootCauses analyzes timeline patterns to suggest root causes.
    // Returns up to maxCauses suggestions ranked by likelihood.
    IdentifyRootCauses(timeline []TimelineEntry, maxCauses int) []string

    // GenerateActionItems creates recommended follow-up actions based on incident analysis.
    // Each action item has a priority and category for tracking.
    GenerateActionItems(report *PostmortemReport) []ActionItem

    // ValidateReport checks report completeness and consistency.
    // Returns list of validation errors (empty if valid).
    ValidateReport(report *PostmortemReport) []string

    // SeverityFromMetrics calculates incident severity (1-5) from impact metrics.
    // Higher values indicate more severe incidents.
    SeverityFromMetrics(metrics ImpactMetrics) int

    // SummarizeBatch generates aggregate statistics across multiple postmortems.
    // Returns trends in MTTR, common root causes, and repeat issues.
    SummarizeBatch(reports []*PostmortemReport) BatchSummary
}

// BatchSummary provides aggregate postmortem statistics.
type BatchSummary struct {
    TotalIncidents     int
    AverageTTD         time.Duration // Average time to detect
    AverageTTR         time.Duration // Average time to respond
    AverageTTRes       time.Duration // Average time to resolve
    TopRootCauses      []RootCauseStat
    OpenActionItems    int
    OverdueActionItems int
}

// RootCauseStat tracks frequency of a root cause.
type RootCauseStat struct {
    Cause      string
    Occurrences int
    Percentage  float64
}
```

### Required Structs

| Struct | Purpose |
|--------|---------|
| `PostmortemReport` | Complete postmortem document with all sections |
| `TimelineEntry` | Single timestamped event in incident timeline |
| `ImpactMetrics` | Quantitative incident impact measurements |
| `ActionItem` | Follow-up task generated from postmortem analysis |
| `BatchSummary` | Aggregate statistics across multiple incidents |
| `RootCauseStat` | Root cause frequency tracking |

### Architectural Patterns to Follow

1. **Internal package pattern**: Core logic in `internal/postmortem/` with pure functions
2. **Service wrapper pattern**: Thin service layer in `services/postmortem/` using `contracts.IncidentCommand` and returning `contracts.IncidentEvent`
3. **Constructor pattern**: `func New() *Generator` for service instantiation
4. **Error handling**: Return errors for invalid states, never panic
5. **Sorting conventions**: Use `sort.Slice` for timeline ordering (ascending by timestamp)

### Acceptance Criteria

1. **Unit tests** (`tests/unit/postmortem_test.go`):
   - Test timeline building with mixed event and audit sources
   - Test metric calculations with edge cases (empty timeline, single event)
   - Test root cause identification with various patterns
   - Test severity calculation thresholds
   - Test batch summary aggregation
   - Minimum 15 test cases

2. **Integration tests** (`tests/integration/postmortem_flow_test.go`):
   - Test full report generation from incident to published postmortem
   - Test integration with existing compliance/audit modules
   - Minimum 5 integration test cases

3. **Code coverage**: >= 80% line coverage for `internal/postmortem/`

4. **Compatibility**:
   - Must use existing `models.Incident`, `contracts.IncidentEvent`, `contracts.AuditEntry`
   - Must integrate with `internal/compliance` for audit data
   - Must integrate with `internal/events` for event correlation

### Test Command

```bash
go test -v ./...
```

---

## Task 2: Alert Grouping Service

### Overview

Implement an **Alert Grouping Service** that intelligently clusters related alerts to reduce alert fatigue and improve incident correlation. This module groups alerts based on temporal proximity, region, severity patterns, and content similarity.

### Location

- Internal package: `internal/alerting/grouper.go`
- Service wrapper: `services/alerting/service.go`

### Interface Contract

```go
package alerting

import (
    "incidentmesh/pkg/models"
    "incidentmesh/shared/contracts"
    "time"
)

// Alert represents an incoming alert from monitoring systems.
type Alert struct {
    AlertID     string
    Source      string            // monitoring system name
    Region      string
    Severity    int               // 1=critical, 2=high, 3=medium, 4=low
    Title       string
    Description string
    Labels      map[string]string // key-value metadata
    FiredAt     time.Time
    ResolvedAt  *time.Time        // nil if still active
    Fingerprint string            // content hash for deduplication
}

// AlertGroup represents a cluster of related alerts.
type AlertGroup struct {
    GroupID        string
    Alerts         []Alert
    Representative Alert           // most severe or first alert in group
    Region         string
    SeverityMax    int
    SeverityMin    int
    CreatedAt      time.Time
    UpdatedAt      time.Time
    Status         string          // "active", "resolved", "silenced"
    IncidentID     *string         // linked incident if escalated
    Annotations    map[string]string
}

// GroupingRule defines criteria for grouping alerts together.
type GroupingRule struct {
    RuleID        string
    Name          string
    MatchLabels   []string        // labels that must match
    TimeWindowSec int             // max time gap between alerts
    SeverityRange []int           // acceptable severity range [min, max]
    RegionMatch   bool            // require same region
    Priority      int             // higher priority rules evaluated first
    Enabled       bool
}

// GroupingConfig holds global grouping settings.
type GroupingConfig struct {
    DefaultTimeWindowSec int
    MaxGroupSize         int
    DeduplicationWindow  time.Duration
    AutoResolveAfter     time.Duration
    Rules                []GroupingRule
}

// Grouper defines the alert grouping interface.
type Grouper interface {
    // GroupAlerts clusters alerts based on configured rules.
    // Returns new or updated groups affected by the incoming alerts.
    GroupAlerts(alerts []Alert, config GroupingConfig) []*AlertGroup

    // FindGroup locates the best matching group for a single alert.
    // Returns nil if no suitable group exists (create new group).
    FindGroup(alert Alert, groups []*AlertGroup, rules []GroupingRule) *AlertGroup

    // MergeGroups combines two groups when overlap is detected.
    // Preserves the most severe representative and all alerts.
    MergeGroups(a, b *AlertGroup) *AlertGroup

    // EvaluateRule checks if an alert matches a grouping rule.
    // Returns match score (0.0-1.0) where 1.0 is perfect match.
    EvaluateRule(alert Alert, group *AlertGroup, rule GroupingRule) float64

    // DeduplicateAlerts removes duplicate alerts by fingerprint.
    // Keeps the earliest occurrence within the deduplication window.
    DeduplicateAlerts(alerts []Alert, windowDuration time.Duration) []Alert

    // SeverityRollup calculates group severity from member alerts.
    // Returns the maximum severity and the severity distribution.
    SeverityRollup(group *AlertGroup) (maxSeverity int, distribution map[int]int)

    // ExpireGroups marks groups as resolved if all alerts are resolved
    // and no new alerts arrived within the auto-resolve window.
    ExpireGroups(groups []*AlertGroup, config GroupingConfig, now time.Time) []*AlertGroup

    // SplitGroup divides a group that has grown too heterogeneous.
    // Returns multiple groups if split occurred, single group otherwise.
    SplitGroup(group *AlertGroup, rules []GroupingRule) []*AlertGroup

    // LinkToIncident associates an alert group with an incident.
    // Updates the group's IncidentID and returns the modified group.
    LinkToIncident(group *AlertGroup, incidentID string) *AlertGroup

    // GroupStatistics computes metrics for monitoring alert patterns.
    // Returns aggregated statistics across all provided groups.
    GroupStatistics(groups []*AlertGroup) GroupStats
}

// GroupStats provides alert grouping metrics.
type GroupStats struct {
    TotalGroups       int
    ActiveGroups      int
    ResolvedGroups    int
    TotalAlerts       int
    AverageGroupSize  float64
    MedianTimeToGroup time.Duration
    DeduplicatedCount int
    LinkedIncidents   int
}

// LabelMatcher computes label similarity between alerts.
type LabelMatcher interface {
    // MatchScore returns similarity (0.0-1.0) between two label sets.
    MatchScore(a, b map[string]string, matchLabels []string) float64

    // RequiredLabelsPresent checks if all required labels exist.
    RequiredLabelsPresent(labels map[string]string, required []string) bool
}
```

### Required Structs

| Struct | Purpose |
|--------|---------|
| `Alert` | Individual alert from monitoring systems |
| `AlertGroup` | Cluster of related alerts |
| `GroupingRule` | Criteria for grouping alerts together |
| `GroupingConfig` | Global grouping configuration |
| `GroupStats` | Aggregate metrics for alert patterns |

### Architectural Patterns to Follow

1. **Stateless design**: Grouper functions take all state as input (no hidden caches)
2. **Score-based matching**: Use float64 scores for fuzzy matching (see `internal/routing/RouteScore`)
3. **Time-window patterns**: Similar to `internal/events/WindowEvents`
4. **Deduplication**: Follow `internal/events/Deduplicate` pattern but correct the bug
5. **Configuration-driven**: Rules loaded from config similar to `internal/config`

### Acceptance Criteria

1. **Unit tests** (`tests/unit/alerting_test.go`):
   - Test grouping with various rule configurations
   - Test deduplication with overlapping fingerprints
   - Test merge and split operations
   - Test severity rollup calculations
   - Test expiration logic with time boundaries
   - Test label matching with partial and complete matches
   - Minimum 20 test cases

2. **Integration tests** (`tests/integration/alerting_flow_test.go`):
   - Test alert ingestion to group formation
   - Test group-to-incident linking with escalation service
   - Test concurrent alert processing
   - Minimum 5 integration test cases

3. **Code coverage**: >= 80% line coverage for `internal/alerting/`

4. **Compatibility**:
   - Must integrate with `internal/triage` for severity handling
   - Must integrate with `services/escalation` for incident linking
   - Must integrate with `internal/events` for correlation

### Test Command

```bash
go test -v ./...
```

---

## Task 3: On-Call Schedule Manager

### Overview

Implement an **On-Call Schedule Manager** that handles responder rotations, overrides, escalation chains, and availability tracking. This module supports multiple schedule layers, holiday handling, and timezone-aware scheduling.

### Location

- Internal package: `internal/oncall/scheduler.go`
- Service wrapper: `services/oncall/service.go`

### Interface Contract

```go
package oncall

import (
    "incidentmesh/shared/contracts"
    "time"
)

// Responder represents an on-call team member.
type Responder struct {
    UserID       string
    Name         string
    Email        string
    Phone        string
    Timezone     string            // IANA timezone (e.g., "America/New_York")
    Teams        []string
    Skills       []string          // ["incident_commander", "sre", "network"]
    Availability AvailabilityRule
}

// AvailabilityRule defines when a responder is available.
type AvailabilityRule struct {
    WorkingHoursStart int  // hour of day (0-23) in responder's timezone
    WorkingHoursEnd   int
    WorkingDays       []time.Weekday
    ExcludeDates      []time.Time   // vacation, holidays
}

// Schedule defines a recurring on-call rotation.
type Schedule struct {
    ScheduleID     string
    Name           string
    TeamID         string
    Timezone       string
    RotationType   string          // "daily", "weekly", "custom"
    RotationLength int             // in days for "custom"
    HandoffTime    int             // hour of day for rotation handoff
    Layers         []ScheduleLayer
    Escalations    []EscalationStep
    CreatedAt      time.Time
    UpdatedAt      time.Time
}

// ScheduleLayer represents one layer of an on-call schedule.
// Multiple layers allow primary, secondary, and shadow rotations.
type ScheduleLayer struct {
    LayerID     string
    Name        string
    Priority    int               // lower = higher priority (1 = primary)
    Responders  []string          // user IDs in rotation order
    StartDate   time.Time
    EndDate     *time.Time        // nil for indefinite
}

// Override temporarily replaces a responder in the schedule.
type Override struct {
    OverrideID    string
    ScheduleID    string
    OriginalUser  string
    ReplacementUser string
    StartTime     time.Time
    EndTime       time.Time
    Reason        string
    CreatedBy     string
    CreatedAt     time.Time
}

// EscalationStep defines who to contact if primary doesn't respond.
type EscalationStep struct {
    StepNumber     int
    DelayMinutes   int             // wait time before escalating
    TargetUserIDs  []string
    TargetType     string          // "user", "team", "manager"
    NotifyChannels []string        // ["sms", "phone", "email", "slack"]
}

// OnCallShift represents a resolved time period with assigned responder.
type OnCallShift struct {
    ShiftID     string
    ScheduleID  string
    ResponderID string
    StartTime   time.Time
    EndTime     time.Time
    Layer       int
    IsOverride  bool
    OverrideID  *string
}

// Scheduler defines the on-call management interface.
type Scheduler interface {
    // ResolveOnCall returns the current on-call responder for a schedule.
    // Considers layers, overrides, and availability in priority order.
    ResolveOnCall(schedule Schedule, overrides []Override, now time.Time) (*Responder, error)

    // GetShifts returns all shifts in a time range for a schedule.
    // Includes override information if applicable.
    GetShifts(schedule Schedule, overrides []Override, start, end time.Time) []OnCallShift

    // CreateOverride adds a temporary schedule override.
    // Returns error if override conflicts with existing overrides.
    CreateOverride(schedule Schedule, override Override, existingOverrides []Override) (*Override, error)

    // ValidateOverride checks if an override is valid.
    // Validates user existence, time bounds, and no conflicts.
    ValidateOverride(override Override, schedule Schedule, existingOverrides []Override) []string

    // CalculateRotation determines who is on-call for a specific time.
    // Returns the responder ID based on rotation position.
    CalculateRotation(layer ScheduleLayer, atTime time.Time, handoffHour int, tz string) string

    // NextHandoff returns the next rotation handoff time.
    // Respects schedule timezone and handoff hour.
    NextHandoff(schedule Schedule, from time.Time) time.Time

    // FindCoverage locates available responders for a time slot.
    // Filters by team, skills, and availability rules.
    FindCoverage(responders []Responder, team string, requiredSkills []string, slot time.Time) []Responder

    // EscalationChain returns the ordered list of responders to contact.
    // Includes delay information for each escalation level.
    EscalationChain(schedule Schedule, incident contracts.IncidentEvent, now time.Time) []EscalationContact

    // CheckAvailability determines if a responder is available at a time.
    // Considers timezone, working hours, and exclusion dates.
    CheckAvailability(responder Responder, at time.Time) bool

    // RotationGaps finds periods with no coverage in a schedule.
    // Returns gaps that need manual override or schedule adjustment.
    RotationGaps(schedule Schedule, overrides []Override, responders []Responder, start, end time.Time) []TimeGap

    // ScheduleStatistics computes on-call burden metrics.
    // Returns hours per responder, coverage percentage, and fairness score.
    ScheduleStatistics(schedule Schedule, overrides []Override, start, end time.Time) ScheduleStats
}

// EscalationContact represents a responder in an escalation chain.
type EscalationContact struct {
    Responder      Responder
    StepNumber     int
    DelayMinutes   int
    NotifyChannels []string
    ContactAt      time.Time
}

// TimeGap represents a period with no on-call coverage.
type TimeGap struct {
    StartTime time.Time
    EndTime   time.Time
    Duration  time.Duration
    Layer     int
    Reason    string // "no_responders", "all_unavailable", "schedule_ended"
}

// ScheduleStats provides on-call burden metrics.
type ScheduleStats struct {
    TotalHours        float64
    CoveragePercent   float64
    HoursPerResponder map[string]float64
    FairnessScore     float64           // 0.0-1.0, higher = more equal distribution
    OverrideCount     int
    GapCount          int
}
```

### Required Structs

| Struct | Purpose |
|--------|---------|
| `Responder` | On-call team member with contact info and availability |
| `Schedule` | Recurring on-call rotation definition |
| `ScheduleLayer` | Single layer (primary/secondary) of a schedule |
| `Override` | Temporary schedule modification |
| `EscalationStep` | Escalation chain configuration |
| `OnCallShift` | Resolved time period with assigned responder |
| `EscalationContact` | Responder in escalation sequence |
| `TimeGap` | Period without coverage |
| `ScheduleStats` | On-call burden metrics |

### Architectural Patterns to Follow

1. **Timezone handling**: Use `time.LoadLocation` for all timezone conversions
2. **Layer priority**: Lower priority number = higher priority (consistent with escalation levels)
3. **Override precedence**: Overrides always take precedence over scheduled rotations
4. **Time boundary patterns**: Similar to `internal/events/WindowEvents` for range queries
5. **Escalation integration**: Compatible with `internal/escalation/EscalationChain`

### Acceptance Criteria

1. **Unit tests** (`tests/unit/oncall_test.go`):
   - Test rotation calculation across day/week boundaries
   - Test override application and conflict detection
   - Test multi-layer schedule resolution
   - Test timezone conversion edge cases (DST transitions)
   - Test availability rule evaluation
   - Test escalation chain building
   - Test gap detection with various schedule configurations
   - Test fairness score calculation
   - Minimum 25 test cases

2. **Integration tests** (`tests/integration/oncall_flow_test.go`):
   - Test end-to-end incident-to-escalation flow
   - Test override creation with notification triggers
   - Test schedule handoff with concurrent incidents
   - Minimum 5 integration test cases

3. **Code coverage**: >= 80% line coverage for `internal/oncall/`

4. **Compatibility**:
   - Must integrate with `internal/escalation` for escalation logic
   - Must integrate with `services/notifications` for responder contact
   - Must use `contracts.IncidentEvent` for incident escalation context

### Test Command

```bash
go test -v ./...
```

---

## General Requirements

### Code Quality

- Follow Go naming conventions (exported functions start with uppercase)
- Include doc comments for all exported types and functions
- Handle errors explicitly (no panic for recoverable errors)
- Use meaningful variable names (not single letters except for loop indices)

### Testing

- Use table-driven tests where appropriate
- Include edge cases (empty inputs, nil values, boundary conditions)
- Test concurrent access where applicable (use `-race` flag)
- Include benchmark tests for performance-critical functions

### Documentation

- Add package-level doc comment explaining the module's purpose
- Document complex algorithms inline
- Include usage examples in test files

### Integration Points

All new modules must integrate cleanly with existing IncidentMesh components:

| Module | Integration Points |
|--------|-------------------|
| Postmortem | `models.Incident`, `contracts.IncidentEvent`, `contracts.AuditEntry`, `internal/compliance` |
| Alert Grouping | `internal/triage`, `services/escalation`, `internal/events` |
| On-Call | `internal/escalation`, `services/notifications`, `contracts.IncidentEvent` |
