# QuorumLedger - Alternative Tasks

## Overview

QuorumLedger supports 5 alternative engineering tasks beyond the core debugging challenge: implementing multi-currency settlement capabilities, refactoring consensus for pluggable voting strategies, optimizing ledger posting performance, extending reconciliation with streaming APIs, and migrating from legacy settlement formats.

## Environment

- **Language**: Go
- **Infrastructure**: PostgreSQL, Redis, NATS
- **Difficulty**: Hyper-Principal
- **Base Bugs**: 980 across 17 categories

## Tasks

### Task 1: Multi-Currency Settlement Netting (Feature Development)

QuorumLedger currently handles settlement netting for single-currency batches, but treasury operations increasingly require cross-currency settlement capabilities. Implement multi-currency netting that aggregates positions across different currencies, applies configurable FX rates during settlement, and computes net obligations in a designated settlement currency. The system must handle currency mismatches gracefully, apply appropriate rounding rules for each currency pair, and maintain audit trails for FX rate applications.

**Key Requirements:**
- Extend `SettlementBatch` model to track original currencies alongside converted amounts
- FX rates applied with configurable precision (2, 4, or 6 decimal places)
- Settlement fees include FX spread component for cross-currency transactions
- Batches with missing FX rates rejected with clear error messages
- Zero-sum validation passes after FX conversion within configured tolerance

### Task 2: Consensus Module Refactoring for Pluggable Voting Strategies (Refactoring)

The current consensus implementation hardcodes Byzantine fault tolerance calculations. Different deployment scenarios require different strategies: regulated environments need unanimous consent, while high-throughput scenarios accept simple majority with weighted voting. Refactor the consensus module to support pluggable voting strategies while maintaining backward compatibility as the default.

**Key Requirements:**
- Define `VotingStrategy` interface for approval ratio, quorum checking, and health assessment
- Extract existing BFT logic into `ByzantineStrategy`
- Implement `WeightedMajorityStrategy` with node-specific vote weights
- Implement `UnanimousStrategy` requiring 100% approval
- Strategy selection configurable at runtime without code changes
- `QuorumHealth`, `HasQuorum`, and `IsSupermajority` delegate to active strategy

### Task 3: Ledger Posting Batch Performance Optimization (Performance Optimization)

Performance profiling identifies ledger posting as a bottleneck during end-of-day runs. The module creates new maps on every invocation, performs redundant iterations, and allocates excessively for large batches. Optimize to handle 100,000+ entry batches efficiently while preserving functional behavior.

**Key Requirements:**
- `ApplyEntries` pre-allocates output map capacity based on input sizes
- `ValidateSequence` returns early on first invalid sequence
- `GroupByAccount` uses size hints to minimize slice reallocations
- Batch operations of 100,000 entries complete within 500ms
- Memory allocations per entry reduced by at least 50%
- All existing tests pass with identical outputs

### Task 4: Reconciliation Streaming API Extension (API Extension)

The reconciliation module operates on complete entry sets in memory. Large-scale operations require streaming reconciliation that processes entries incrementally, emits partial results, and resumes from checkpoints after interruption. Extend the reconciliation API to support streaming operations with iterator-based processing.

**Key Requirements:**
- `StreamingReconciler` type processes entries via iterator interface
- `EmitPartialReport` yields current state without completing operation
- `CreateCheckpoint` serializes reconciler state for later resumption
- `ResumeFromCheckpoint` restores state and continues processing
- `DeltaReconcile` processes entries changed since a timestamp
- Partial reports include progress indicators and estimated remaining work
- Cancellation via context properly cleans up resources

### Task 5: Legacy Settlement Format Migration (Migration)

QuorumLedger is migrating from legacy floating-point dollar amounts to integer cents representation. Implement a migration module that converts historical data, validates conversion accuracy, and supports a transition period where both formats coexist.

**Key Requirements:**
- `MigrateLegacyBatch` converts floating-point dollars to integer cents with proper rounding
- Conversion validates that `abs(original - converted/100) < 0.005` for each entry
- `DualFormatBatch` structure supports both legacy and current representations
- `ValidateMigration` compares legacy and migrated batches for value equivalence
- `RollbackMigration` restores original values if post-migration validation fails
- Currency-specific decimal handling (JPY=0, most currencies=2)
- Audit records capture migration timestamp, original values, and conversion details

## Getting Started

```bash
go test -v ./...
```

Review tests, trace failures to source modules in `internal/`, `pkg/models/`, `shared/contracts/`, and `services/`.

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). All corresponding unit tests pass and existing tests remain unaffected.
