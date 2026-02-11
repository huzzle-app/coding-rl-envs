# QuorumLedger - Alternative Tasks

These alternative tasks represent realistic work items for a distributed ledger platform handling quorum consensus, settlement netting, and treasury operations.

---

## Task 1: Multi-Currency Settlement Netting (Feature Development)

### Description

QuorumLedger currently handles settlement netting for single-currency batches, but treasury operations increasingly require cross-currency settlement capabilities. The platform needs to support multilateral netting across currency pairs with real-time FX rate application.

Implement multi-currency netting that aggregates positions across different currencies, applies configurable FX rates during settlement, and computes net obligations in a designated settlement currency. The system must handle currency mismatches gracefully, apply appropriate rounding rules for each currency pair, and maintain audit trails for FX rate applications.

The feature should integrate with the existing `settlement/netting.go` module and extend the `SettlementBatch` model to track original currencies alongside converted amounts. Settlement fee calculations must account for FX spread when cross-currency transactions are involved.

### Acceptance Criteria

- Multi-currency settlement batches compute net positions across all currencies using provided FX rates
- FX rates are applied with configurable precision (2, 4, or 6 decimal places) per currency pair
- Settlement fees include FX spread component for cross-currency transactions
- Batches with missing FX rates for required currency pairs are rejected with clear error messages
- Audit records capture original amounts, applied FX rates, and converted amounts
- Net position calculations handle both bilateral and multilateral cross-currency scenarios
- Zero-sum validation passes after FX conversion within configured tolerance threshold
- Existing single-currency settlement behavior remains unchanged

### Test Command

```bash
go test -v ./...
```

---

## Task 2: Consensus Module Refactoring for Pluggable Voting Strategies (Refactoring)

### Description

The current consensus implementation in `internal/consensus/quorum.go` hardcodes Byzantine fault tolerance calculations and supermajority thresholds. Different deployment scenarios require different consensus strategies: some regulated environments mandate unanimous consent, while high-throughput scenarios accept simple majority with weighted voting.

Refactor the consensus module to support pluggable voting strategies through a strategy interface. The refactoring should extract the current BFT logic into a concrete strategy implementation while enabling alternative strategies like weighted quorum, unanimous consent, and tiered approval (different thresholds for different transaction types).

The refactored design must maintain backward compatibility with existing consensus behavior as the default strategy. All existing functions should delegate to the configured strategy, and strategy selection should be configurable at runtime without code changes.

### Acceptance Criteria

- Define a `VotingStrategy` interface with methods for approval ratio calculation, quorum checking, and health assessment
- Extract existing BFT logic into `ByzantineStrategy` implementing the interface
- Implement `WeightedMajorityStrategy` supporting node-specific vote weights
- Implement `UnanimousStrategy` requiring 100% approval for quorum
- Default strategy produces identical results to current hardcoded behavior
- Strategy can be selected via configuration without code modifications
- `QuorumHealth`, `HasQuorum`, and `IsSupermajority` delegate to active strategy
- No changes to function signatures in the public API

### Test Command

```bash
go test -v ./...
```

---

## Task 3: Ledger Posting Batch Performance Optimization (Performance Optimization)

### Description

Performance profiling has identified the ledger posting module as a bottleneck during end-of-day settlement runs. The `ApplyEntries` function creates new maps on every invocation, `ValidateSequence` performs redundant iterations, and `GroupByAccount` allocates excessively when processing large entry batches.

Optimize the ledger posting module to handle batch sizes of 100,000+ entries efficiently. Focus on reducing memory allocations, eliminating redundant iterations, and enabling concurrent processing where account independence allows. The optimizations must not change the functional behavior or output of any existing functions.

Consider implementing pre-allocation strategies based on input size hints, batch validation that short-circuits on first failure, and concurrent balance calculations for independent accounts. Memory pooling for intermediate data structures may provide significant benefits for repeated batch processing.

### Acceptance Criteria

- `ApplyEntries` pre-allocates output map capacity based on input sizes
- `ValidateSequence` returns early on first invalid sequence without full iteration
- `GroupByAccount` uses size hints to minimize slice reallocations
- `HighValueEntries` processes entries without intermediate allocations for small batches
- Batch operations of 100,000 entries complete within 500ms on standard hardware
- Memory allocations per entry reduced by at least 50% compared to baseline
- All existing tests pass with identical outputs
- No goroutine leaks or race conditions introduced

### Test Command

```bash
go test -v ./...
```

---

## Task 4: Reconciliation Streaming API Extension (API Extension)

### Description

The reconciliation module currently operates on complete entry sets loaded into memory. Large-scale treasury operations require streaming reconciliation that can process entries incrementally, emit partial results, and resume from checkpoints after interruption.

Extend the reconciliation API to support streaming operations. Add iterator-based entry processing that yields match results incrementally, checkpoint creation for long-running reconciliation jobs, and delta reconciliation that processes only entries changed since a previous checkpoint.

The streaming API should integrate with the existing `ReconciliationReport` structure while enabling progressive updates. Partial reports should be distinguishable from complete reports, and streaming operations must support cancellation without corrupting state.

### Acceptance Criteria

- `StreamingReconciler` type processes entries via an iterator interface rather than full slices
- `EmitPartialReport` yields current reconciliation state without completing the full operation
- `CreateCheckpoint` serializes reconciler state for later resumption
- `ResumeFromCheckpoint` restores reconciler state and continues processing
- `DeltaReconcile` accepts entries changed since a timestamp and updates existing report
- Partial reports include progress indicators (entries processed, estimated remaining)
- Cancellation via context properly cleans up resources and returns partial results
- Existing batch reconciliation functions remain unchanged and functional

### Test Command

```bash
go test -v ./...
```

---

## Task 5: Legacy Settlement Format Migration (Migration)

### Description

QuorumLedger is migrating from a legacy settlement format that stored amounts as floating-point dollars to the current integer cents representation. The migration must handle historical data conversion, validate conversion accuracy, and support a transition period where both formats may coexist.

Implement a migration module that converts legacy settlement batches to the current format, validates that conversion preserves value within acceptable tolerance, and provides rollback capabilities if validation fails. The migration must handle edge cases like currency-specific decimal places, historical FX rates, and legacy batch identifiers.

The migration should support both one-time bulk conversion and ongoing dual-format operation during the transition period. Audit trails must clearly indicate which records have been migrated and preserve original values for regulatory compliance.

### Acceptance Criteria

- `MigrateLegacyBatch` converts floating-point dollar amounts to integer cents with proper rounding
- Conversion validates that `abs(original - converted/100) < 0.005` for each entry
- Failed conversions are logged with original values and do not modify the batch
- `DualFormatBatch` structure supports both legacy and current representations simultaneously
- `ValidateMigration` compares legacy and migrated batches for value equivalence
- `RollbackMigration` restores original values if post-migration validation fails
- Audit records capture migration timestamp, original values, and conversion details
- Currency-specific decimal handling (JPY has 0 decimals, most currencies have 2)

### Test Command

```bash
go test -v ./...
```
