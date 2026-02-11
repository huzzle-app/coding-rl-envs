# QuorumLedger Greenfield Tasks

These tasks require implementing NEW modules from scratch following the existing architectural patterns in QuorumLedger. Each task defines interfaces, types, and acceptance criteria for building production-ready components for the distributed ledger platform.

**Test Command:** `go test -v ./...`

---

## Task 1: Cross-Ledger Bridge Service

### Overview

Implement a Cross-Ledger Bridge module that enables atomic transfers between multiple independent ledger instances. The bridge must coordinate settlements across ledgers while maintaining consistency guarantees and handling partial failures.

### Module Location

- Internal logic: `internal/bridge/transfer.go`
- Service wrapper: `services/bridge/service.go`

### Interface Contract

```go
// internal/bridge/transfer.go
package bridge

import "quorumledger/pkg/models"

// BridgeTransfer represents a cross-ledger transfer request
type BridgeTransfer struct {
    ID              string
    SourceLedgerID  string
    TargetLedgerID  string
    SourceAccount   string
    TargetAccount   string
    AmountCents     int64
    Currency        string
    InitiatedEpoch  int64
    Status          BridgeStatus
    LockID          string    // Lock on source funds
    ConfirmationID  string    // Confirmation from target ledger
}

type BridgeStatus int

const (
    BridgeStatusPending     BridgeStatus = 0  // Transfer initiated
    BridgeStatusLocked      BridgeStatus = 1  // Source funds locked
    BridgeStatusConfirmed   BridgeStatus = 2  // Target ledger confirmed receipt
    BridgeStatusSettled     BridgeStatus = 3  // Both sides settled
    BridgeStatusRolledBack  BridgeStatus = 4  // Transfer failed and rolled back
    BridgeStatusExpired     BridgeStatus = 5  // Lock expired without confirmation
)

// LockResult represents the outcome of a fund lock operation
type LockResult struct {
    LockID      string
    Success     bool
    LockedAt    int64
    ExpiresAt   int64
    Reason      string
}

// SettlementProof represents proof of settlement for audit purposes
type SettlementProof struct {
    TransferID      string
    SourceChecksum  string
    TargetChecksum  string
    SettledEpoch    int64
    WitnessNodes    []string
}

// InitiateTransfer creates a new cross-ledger transfer request.
// Returns error if source account has insufficient funds or ledger is unreachable.
func InitiateTransfer(sourceEntry models.LedgerEntry, targetLedgerID, targetAccount string) (*BridgeTransfer, error)

// LockFunds places a hold on source funds pending target confirmation.
// Lock must expire after lockDurationSeconds if not confirmed.
// Returns LockResult with lock details or failure reason.
func LockFunds(transfer *BridgeTransfer, lockDurationSeconds int) LockResult

// ConfirmReceipt records target ledger's confirmation of fund receipt.
// Must validate that confirmationID matches expected format.
// Returns true if confirmation accepted, false if transfer not in correct state.
func ConfirmReceipt(transfer *BridgeTransfer, confirmationID string) bool

// SettleTransfer finalizes the transfer on both ledgers.
// Must generate SettlementProof for audit trail.
// Returns proof if successful, nil if settlement failed.
func SettleTransfer(transfer *BridgeTransfer, witnessNodes []string) *SettlementProof

// RollbackTransfer reverses a failed transfer, releasing locked funds.
// Can only rollback transfers in Locked or Pending status.
// Returns true if rollback successful, false otherwise.
func RollbackTransfer(transfer *BridgeTransfer) bool

// ExpireLocks processes all transfers with expired locks.
// Returns slice of transfer IDs that were expired.
func ExpireLocks(transfers []*BridgeTransfer, currentEpoch int64) []string

// ValidateBridgeChain verifies a sequence of bridge transfers forms valid chain.
// Checks that each transfer's target matches next transfer's source.
func ValidateBridgeChain(transfers []*BridgeTransfer) bool

// ComputeBridgeFee calculates fee for cross-ledger transfer.
// Fee is basisPoints/10000 of amount, minimum 100 cents.
func ComputeBridgeFee(amountCents int64, basisPoints int) int64

// NetBridgeExposure calculates net exposure across all active bridge transfers.
// Groups by currency and returns absolute value of net position per currency.
func NetBridgeExposure(transfers []*BridgeTransfer) map[string]int64
```

### Required Types

Add to `pkg/models/models.go`:
```go
type BridgeLedger struct {
    ID          string
    Name        string
    Endpoint    string
    IsActive    bool
    LastSyncEpoch int64
}
```

### Service Wrapper

```go
// services/bridge/service.go
package bridge

const Name = "bridge"
const Role = "cross-ledger atomic transfers"

// Service functions should delegate to internal/bridge package
// following the pattern used by services/consensus/service.go
```

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/bridge_test.go`):
   - TestInitiateTransfer: Valid transfer creation
   - TestLockFunds: Lock succeeds with valid duration
   - TestLockFundsExpiration: Lock expires correctly
   - TestConfirmReceipt: Confirmation transitions state correctly
   - TestSettleTransfer: Settlement produces valid proof
   - TestRollbackTransfer: Rollback releases locked funds
   - TestExpireLocks: Batch expiration processes correctly
   - TestValidateBridgeChain: Chain validation works for valid/invalid chains
   - TestComputeBridgeFee: Fee calculation with minimum enforcement
   - TestNetBridgeExposure: Exposure aggregation by currency

2. **Integration Points**:
   - Add "bridge" entry to `shared/contracts/ServiceTopology` with dependencies: `["ledger", "security", "audit"]`
   - Add "bridge" SLO to `shared/contracts/ServiceSLO`: `{"latency_ms": 200, "availability": 0.9985}`

3. **Coverage**: >= 80% line coverage for `internal/bridge/transfer.go`

---

## Task 2: Compliance Reporting Engine

### Overview

Implement a Compliance Reporting Engine that generates regulatory reports from ledger activity. The engine must support configurable report templates, date range filtering, aggregation rules, and export formats. Reports must be immutable once generated and traceable in the audit trail.

### Module Location

- Internal logic: `internal/compliance/reporting.go`
- Service wrapper: `services/compliance/service.go`

### Interface Contract

```go
// internal/compliance/reporting.go
package compliance

import (
    "quorumledger/pkg/models"
    "time"
)

// ReportType defines the category of compliance report
type ReportType int

const (
    ReportTypeTransaction   ReportType = 0  // Transaction summary
    ReportTypeRiskExposure  ReportType = 1  // Risk exposure analysis
    ReportTypeAuditTrail    ReportType = 2  // Audit trail extract
    ReportTypeSettlement    ReportType = 3  // Settlement reconciliation
    ReportTypeRegulatory    ReportType = 4  // Regulatory filing (SAR, CTR)
)

// ReportStatus tracks report lifecycle
type ReportStatus int

const (
    ReportStatusDraft       ReportStatus = 0
    ReportStatusGenerated   ReportStatus = 1
    ReportStatusReviewed    ReportStatus = 2
    ReportStatusApproved    ReportStatus = 3
    ReportStatusSubmitted   ReportStatus = 4
    ReportStatusArchived    ReportStatus = 5
)

// ComplianceReport represents a generated compliance report
type ComplianceReport struct {
    ID              string
    Type            ReportType
    Status          ReportStatus
    GeneratedAt     time.Time
    GeneratedBy     string
    PeriodStart     time.Time
    PeriodEnd       time.Time
    Checksum        string        // Immutability verification
    Summary         ReportSummary
    Entries         []ReportEntry
}

// ReportSummary provides aggregate statistics for the report
type ReportSummary struct {
    TotalTransactions   int
    TotalVolumeCents    int64
    UniqueAccounts      int
    HighRiskCount       int
    FlaggedCount        int
}

// ReportEntry represents a single line item in the report
type ReportEntry struct {
    Timestamp       time.Time
    TransactionID   string
    Account         string
    AmountCents     int64
    Currency        string
    RiskScore       float64
    Flags           []string
}

// ReportFilter defines criteria for filtering report data
type ReportFilter struct {
    AccountPatterns []string   // Glob patterns for account matching
    MinAmountCents  int64
    MaxAmountCents  int64
    Currencies      []string
    RiskThreshold   float64    // Minimum risk score to include
    IncludeFlags    []string   // Must have at least one of these flags
    ExcludeFlags    []string   // Must not have any of these flags
}

// GenerateReport creates a new compliance report for the specified period.
// Applies filter criteria and computes checksum for immutability.
// Returns error if period is invalid or data access fails.
func GenerateReport(
    reportType ReportType,
    entries []models.LedgerEntry,
    auditRecords []models.AuditRecord,
    periodStart, periodEnd time.Time,
    filter ReportFilter,
    generatedBy string,
) (*ComplianceReport, error)

// ComputeReportChecksum generates SHA-256 checksum of report contents.
// Must include all entries and summary data for tamper detection.
func ComputeReportChecksum(report *ComplianceReport) string

// ValidateReportIntegrity verifies report has not been modified.
// Recomputes checksum and compares to stored value.
func ValidateReportIntegrity(report *ComplianceReport) bool

// TransitionReportStatus moves report to next status in workflow.
// Validates transition is allowed (e.g., Draft->Generated, not Draft->Submitted).
// Returns true if transition successful.
func TransitionReportStatus(report *ComplianceReport, newStatus ReportStatus, actor string) bool

// FilterEntries applies ReportFilter to ledger entries.
// Returns entries matching all specified criteria.
func FilterEntries(entries []models.LedgerEntry, filter ReportFilter) []models.LedgerEntry

// ComputeRiskScore calculates risk score for a ledger entry.
// Score based on amount thresholds, account patterns, and velocity.
// Returns score in range [0.0, 1.0].
func ComputeRiskScore(entry models.LedgerEntry, accountHistory []models.LedgerEntry) float64

// FlagTransaction identifies compliance flags for an entry.
// Possible flags: "high_value", "rapid_movement", "new_account",
// "round_amount", "structured", "cross_border"
func FlagTransaction(entry models.LedgerEntry, accountHistory []models.LedgerEntry) []string

// AggregateByPeriod groups entries by time period (hour, day, week, month).
// Returns map of period key to aggregated volume.
func AggregateByPeriod(entries []models.LedgerEntry, periodType string) map[string]int64

// MergeReports combines multiple reports into a consolidated report.
// Reports must be of same type and non-overlapping periods.
// Returns error if reports are incompatible.
func MergeReports(reports []*ComplianceReport) (*ComplianceReport, error)
```

### Required Types

Add to `pkg/models/models.go`:
```go
type ComplianceFlag struct {
    Code        string
    Description string
    Severity    int  // 1=Low, 2=Medium, 3=High, 4=Critical
}
```

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/compliance_test.go`):
   - TestGenerateReport: Report generation with various filters
   - TestComputeReportChecksum: Checksum determinism
   - TestValidateReportIntegrity: Integrity check passes/fails correctly
   - TestTransitionReportStatus: Valid/invalid status transitions
   - TestFilterEntries: Filter by amount, currency, account patterns
   - TestComputeRiskScore: Risk scoring thresholds
   - TestFlagTransaction: Flag detection for each flag type
   - TestAggregateByPeriod: Aggregation for hour/day/week/month
   - TestMergeReports: Merge compatible/incompatible reports

2. **Integration Points**:
   - Add "compliance" to `shared/contracts/ServiceTopology` with dependencies: `["ledger", "audit", "risk"]`
   - Add "compliance" SLO: `{"latency_ms": 500, "availability": 0.9950}`

3. **Coverage**: >= 80% line coverage for `internal/compliance/reporting.go`

---

## Task 3: Event Sourcing Journal

### Overview

Implement an Event Sourcing Journal that captures all state changes as immutable events. The journal supports event replay for state reconstruction, snapshots for optimization, and projections for derived views. Events must be ordered, deduplicated, and cryptographically linked.

### Module Location

- Internal logic: `internal/journal/events.go`
- Service wrapper: `services/journal/service.go`

### Interface Contract

```go
// internal/journal/events.go
package journal

import (
    "time"
)

// EventType categorizes journal events
type EventType int

const (
    EventTypeTransfer       EventType = 0
    EventTypeSettlement     EventType = 1
    EventTypeConsensus      EventType = 2
    EventTypePolicyChange   EventType = 3
    EventTypeRiskAlert      EventType = 4
    EventTypeAuditMarker    EventType = 5
)

// JournalEvent represents an immutable event in the journal
type JournalEvent struct {
    SequenceNum     int64       // Globally ordered sequence number
    EventID         string      // Unique event identifier
    EventType       EventType
    AggregateID     string      // Entity this event belongs to (e.g., account ID)
    Timestamp       time.Time
    Payload         []byte      // JSON-encoded event data
    PrevHash        string      // Hash of previous event (chain integrity)
    Hash            string      // Hash of this event
    CausationID     string      // ID of event that caused this one
    CorrelationID   string      // ID linking related events
}

// Snapshot represents a point-in-time state for faster replay
type Snapshot struct {
    SnapshotID      string
    AggregateID     string
    SequenceNum     int64       // Sequence number at snapshot time
    Timestamp       time.Time
    State           []byte      // JSON-encoded aggregate state
    Hash            string
}

// Projection represents a derived view from events
type Projection struct {
    Name            string
    LastSequence    int64
    State           map[string]interface{}
}

// JournalConfig defines journal behavior settings
type JournalConfig struct {
    SnapshotInterval    int     // Create snapshot every N events
    RetentionDays       int     // Days to retain events before archival
    MaxReplayBatchSize  int     // Maximum events to replay in one batch
    EnableCompression   bool    // Compress payloads
}

// AppendEvent adds a new event to the journal.
// Assigns sequence number, computes hash, and links to previous event.
// Returns error if event validation fails or duplicate detected.
func AppendEvent(event *JournalEvent, prevEvent *JournalEvent) error

// ComputeEventHash generates cryptographic hash for an event.
// Hash covers: SequenceNum, EventID, EventType, AggregateID, Timestamp, Payload, PrevHash
func ComputeEventHash(event *JournalEvent) string

// ValidateEventChain verifies hash chain integrity for a sequence of events.
// Returns (valid, firstInvalidIndex) - if valid, index is -1.
func ValidateEventChain(events []*JournalEvent) (bool, int)

// ReplayEvents reconstructs state by replaying events for an aggregate.
// Starts from snapshot if available, then applies subsequent events.
// Returns final state as map and last processed sequence number.
func ReplayEvents(
    aggregateID string,
    events []*JournalEvent,
    snapshot *Snapshot,
    applyFunc func(state map[string]interface{}, event *JournalEvent) map[string]interface{},
) (map[string]interface{}, int64)

// CreateSnapshot creates a point-in-time snapshot for an aggregate.
// Computes hash of state for integrity verification.
func CreateSnapshot(aggregateID string, state map[string]interface{}, sequenceNum int64) *Snapshot

// GetEventsAfter retrieves events with sequence number > afterSeq.
// Returns at most limit events, ordered by sequence.
func GetEventsAfter(events []*JournalEvent, afterSeq int64, limit int) []*JournalEvent

// GetEventsByAggregate retrieves all events for a specific aggregate.
// Returns events in sequence order.
func GetEventsByAggregate(events []*JournalEvent, aggregateID string) []*JournalEvent

// GetEventsByCorrelation retrieves events with matching correlation ID.
// Useful for tracing related events across aggregates.
func GetEventsByCorrelation(events []*JournalEvent, correlationID string) []*JournalEvent

// DeduplicateEvents removes events with duplicate EventIDs.
// Keeps first occurrence based on sequence number.
func DeduplicateEvents(events []*JournalEvent) []*JournalEvent

// CompactEvents removes events before a snapshot for an aggregate.
// Returns compacted event list and number of events removed.
func CompactEvents(events []*JournalEvent, snapshot *Snapshot) ([]*JournalEvent, int)

// UpdateProjection applies new events to update a projection.
// Calls projector function for each event to update projection state.
func UpdateProjection(
    projection *Projection,
    events []*JournalEvent,
    projector func(state map[string]interface{}, event *JournalEvent) map[string]interface{},
) *Projection

// EventsInTimeRange returns events within the specified time window.
// Inclusive of start, exclusive of end.
func EventsInTimeRange(events []*JournalEvent, start, end time.Time) []*JournalEvent

// GroupByAggregate groups events by their aggregate ID.
// Returns map of aggregateID to event slice.
func GroupByAggregate(events []*JournalEvent) map[string][]*JournalEvent
```

### Required Types

Add to `pkg/models/models.go`:
```go
type EventMetadata struct {
    Source      string    // Service that generated the event
    Version     int       // Event schema version
    Tags        []string  // Searchable tags
}
```

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/journal_test.go`):
   - TestAppendEvent: Event appending with hash chaining
   - TestComputeEventHash: Hash determinism and correctness
   - TestValidateEventChain: Chain validation for valid/broken chains
   - TestReplayEvents: State reconstruction from events
   - TestReplayEventsWithSnapshot: Replay starting from snapshot
   - TestCreateSnapshot: Snapshot creation and hash computation
   - TestGetEventsAfter: Sequence-based filtering with limits
   - TestGetEventsByAggregate: Aggregate filtering
   - TestGetEventsByCorrelation: Correlation ID filtering
   - TestDeduplicateEvents: Duplicate removal by EventID
   - TestCompactEvents: Event compaction around snapshots
   - TestUpdateProjection: Projection updates
   - TestEventsInTimeRange: Time-based filtering
   - TestGroupByAggregate: Event grouping

2. **Integration Points**:
   - Add "journal" to `shared/contracts/ServiceTopology` with dependencies: `["audit", "replay"]`
   - Add "journal" SLO: `{"latency_ms": 50, "availability": 0.9998}`
   - Add "journal" to `RequiredEventFields` in contracts

3. **Coverage**: >= 85% line coverage for `internal/journal/events.go`

---

## General Requirements for All Tasks

### Architectural Patterns

Follow existing patterns demonstrated in the codebase:

1. **Package Structure**:
   - Internal logic in `internal/<module>/<file>.go`
   - Service wrappers in `services/<module>/service.go`
   - Models in `pkg/models/models.go`
   - Contracts in `shared/contracts/contracts.go`

2. **Service Constants**:
   ```go
   const Name = "servicename"
   const Role = "brief description"
   ```

3. **Function Style**:
   - Pure functions preferred (no global state)
   - Return values before error (if applicable)
   - Use explicit types from `pkg/models`

4. **Error Handling**:
   - Return explicit error types where appropriate
   - No panics in production code
   - Validate inputs at function entry

### Test Patterns

Follow test organization from existing tests:

```go
package unit_test

import (
    "testing"
    "quorumledger/internal/<module>"
    "quorumledger/pkg/models"
)

func Test<FunctionName>(t *testing.T) {
    // Arrange
    // Act
    // Assert with t.Fatalf on failure
}
```

### Integration Checklist

- [ ] Internal package created with all interface functions
- [ ] Service wrapper delegates to internal package
- [ ] Models added to `pkg/models/models.go`
- [ ] ServiceTopology updated with new service
- [ ] ServiceSLO updated with latency/availability targets
- [ ] Unit tests pass with >= 80% coverage
- [ ] `go test -v ./...` runs without errors
- [ ] No race conditions (`go test -race ./...`)
