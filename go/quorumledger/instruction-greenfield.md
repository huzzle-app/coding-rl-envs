# QuorumLedger - Greenfield Tasks

## Overview

QuorumLedger supports 3 greenfield implementation tasks requiring creation of production-ready modules from scratch. Each task defines interfaces, types, and acceptance criteria for building new components following existing architectural patterns.

## Environment

- **Language**: Go
- **Infrastructure**: PostgreSQL, Redis, NATS
- **Difficulty**: Hyper-Principal
- **Base Bugs**: 980 across 17 categories

## Tasks

### Task 1: Cross-Ledger Bridge Service (Greenfield Implementation)

Implement a Cross-Ledger Bridge module that enables atomic transfers between multiple independent ledger instances. The bridge must coordinate settlements across ledgers while maintaining consistency guarantees and handling partial failures.

**Module Location:**
- Internal logic: `internal/bridge/transfer.go`
- Service wrapper: `services/bridge/service.go`

**Key Interface Functions:**
- `InitiateTransfer` - Creates new cross-ledger transfer request
- `LockFunds` - Places hold on source funds with expiration
- `ConfirmReceipt` - Records target ledger's confirmation
- `SettleTransfer` - Finalizes transfer and generates settlement proof
- `RollbackTransfer` - Reverses failed transfer, releasing locked funds
- `ExpireLocks` - Processes all transfers with expired locks
- `ValidateBridgeChain` - Verifies sequence of transfers forms valid chain
- `ComputeBridgeFee` - Calculates fee (basisPoints/10000 of amount, minimum 100 cents)
- `NetBridgeExposure` - Calculates net exposure grouped by currency

**Key Types:**
- `BridgeTransfer` - Cross-ledger transfer with status tracking
- `BridgeStatus` - Transfer state (Pending, Locked, Confirmed, Settled, RolledBack, Expired)
- `LockResult` - Outcome of fund lock operation
- `SettlementProof` - Proof of settlement for audit trail
- `BridgeLedger` - Target ledger specification

**Acceptance Criteria:**
- 10 unit tests covering transfer lifecycle, expiration, validation, and fee calculation
- ServiceTopology entry with dependencies: ["ledger", "security", "audit"]
- ServiceSLO: {"latency_ms": 200, "availability": 0.9985}
- >= 80% line coverage for `internal/bridge/transfer.go`

### Task 2: Compliance Reporting Engine (Greenfield Implementation)

Implement a Compliance Reporting Engine that generates regulatory reports from ledger activity. The engine must support configurable report templates, date range filtering, aggregation rules, and export formats. Reports must be immutable once generated and traceable in the audit trail.

**Module Location:**
- Internal logic: `internal/compliance/reporting.go`
- Service wrapper: `services/compliance/service.go`

**Key Interface Functions:**
- `GenerateReport` - Creates compliance report for specified period with filter criteria
- `ComputeReportChecksum` - Generates SHA-256 checksum for tamper detection
- `ValidateReportIntegrity` - Verifies report not modified by recomputing checksum
- `TransitionReportStatus` - Moves report through workflow (Draft→Generated→Reviewed→Approved→Submitted→Archived)
- `FilterEntries` - Applies ReportFilter criteria to ledger entries
- `ComputeRiskScore` - Calculates risk score [0.0, 1.0] based on thresholds and velocity
- `FlagTransaction` - Identifies compliance flags (high_value, rapid_movement, new_account, round_amount, structured, cross_border)
- `AggregateByPeriod` - Groups entries by period (hour/day/week/month)
- `MergeReports` - Combines compatible reports into consolidated report

**Key Types:**
- `ComplianceReport` - Generated report with checksum, status tracking, entries
- `ReportType` - Transaction, RiskExposure, AuditTrail, Settlement, Regulatory
- `ReportStatus` - Draft, Generated, Reviewed, Approved, Submitted, Archived
- `ReportSummary` - Aggregate statistics
- `ReportEntry` - Single line item with risk score and flags
- `ReportFilter` - Account patterns, amount ranges, currency filters
- `ComplianceFlag` - Code, description, severity levels

**Acceptance Criteria:**
- 9 unit tests covering generation, filtering, risk scoring, flag detection, and merging
- ServiceTopology entry with dependencies: ["ledger", "audit", "risk"]
- ServiceSLO: {"latency_ms": 500, "availability": 0.9950}
- >= 80% line coverage for `internal/compliance/reporting.go`

### Task 3: Event Sourcing Journal (Greenfield Implementation)

Implement an Event Sourcing Journal that captures all state changes as immutable events. The journal supports event replay for state reconstruction, snapshots for optimization, and projections for derived views. Events must be ordered, deduplicated, and cryptographically linked.

**Module Location:**
- Internal logic: `internal/journal/events.go`
- Service wrapper: `services/journal/service.go`

**Key Interface Functions:**
- `AppendEvent` - Adds event, assigns sequence, computes hash, links to previous
- `ComputeEventHash` - Generates cryptographic hash covering all event fields
- `ValidateEventChain` - Verifies hash chain integrity, returns (valid bool, firstInvalidIndex int)
- `ReplayEvents` - Reconstructs state by replaying events with optional snapshot
- `CreateSnapshot` - Creates point-in-time state snapshot with hash
- `GetEventsAfter` - Retrieves events with sequence > afterSeq, up to limit
- `GetEventsByAggregate` - Retrieves all events for specific aggregate ID
- `GetEventsByCorrelation` - Retrieves events with matching correlation ID
- `DeduplicateEvents` - Removes duplicate EventIDs, keeps first by sequence
- `CompactEvents` - Removes events before snapshot, returns compacted list and count
- `UpdateProjection` - Applies events to update derived view projection
- `EventsInTimeRange` - Returns events within time window (inclusive start, exclusive end)
- `GroupByAggregate` - Groups events by aggregate ID

**Key Types:**
- `JournalEvent` - Immutable event with sequence, hash chain, causation tracking
- `EventType` - Transfer, Settlement, Consensus, PolicyChange, RiskAlert, AuditMarker
- `Snapshot` - Point-in-time state for faster replay
- `Projection` - Derived view from events with incremental updates
- `JournalConfig` - Snapshot interval, retention days, replay batch size, compression
- `EventMetadata` - Source, version, tags for searchability

**Acceptance Criteria:**
- 14 unit tests covering append, hash validation, replay, snapshots, filtering, projections
- ServiceTopology entry with dependencies: ["audit", "replay"]
- ServiceSLO: {"latency_ms": 50, "availability": 0.9998}
- >= 85% line coverage for `internal/journal/events.go`

## Getting Started

```bash
go test -v ./...
```

## Architectural Patterns

Follow existing patterns demonstrated in the codebase:

1. **Package Structure**: Internal logic in `internal/<module>/<file>.go`, service wrappers in `services/<module>/service.go`, models in `pkg/models/models.go`

2. **Service Constants**: Define `const Name = "servicename"` and `const Role = "description"` in service package

3. **Function Style**: Pure functions preferred, return values before error, use explicit types from `pkg/models`

4. **Error Handling**: Return explicit error types, no panics, validate inputs at function entry

## Success Criteria

Implementation meets all acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). All unit tests pass with required coverage, services integrate properly, and `go test -v ./...` runs without errors or race conditions.
