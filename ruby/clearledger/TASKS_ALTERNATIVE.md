# ClearLedger - Alternative Tasks

This document contains alternative tasks for the ClearLedger financial ledger platform. Each task focuses on a different aspect of software engineering within the clearing and settlement domain.

---

## Task 1: Multi-Currency Settlement Netting (Feature Development)

### Description

ClearLedger currently handles single-currency settlement batches, but clients are requesting support for multi-currency netting within the same settlement window. The settlement engine needs to be extended to group entries by currency, compute net positions per currency, apply currency-specific reserve ratios, and produce consolidated settlement instructions.

The feature must maintain backward compatibility with existing single-currency workflows while enabling cross-currency netting for eligible counterparties. Currency conversion should happen at the final settlement stage using provided FX rates, with appropriate rounding rules for each currency pair. The system must also track gross and net exposure per currency for risk reporting.

### Acceptance Criteria

- Settlement module supports grouping entries by currency code before computing net positions
- Reserve ratios can be configured per currency (e.g., 2% for USD, 3% for EUR, 5% for emerging market currencies)
- Multi-currency batches produce a consolidated net position converted to a base settlement currency
- FX rate application uses mid-market rates with configurable spread for buy/sell sides
- Netting ratio calculations account for currency-adjusted gross exposure
- Settlement fees tier appropriately based on the total converted settlement amount
- Existing single-currency settlement tests continue to pass without modification
- All new multi-currency paths have corresponding test coverage

### Test Command

```bash
bundle exec rspec
```

---

## Task 2: Reconciliation Engine Refactoring (Refactoring)

### Description

The reconciliation module has grown organically and now contains tightly coupled logic for mismatch detection, snapshot merging, break counting, and drift scoring. This coupling makes it difficult to add new reconciliation strategies (e.g., fuzzy matching, temporal windowed reconciliation) and complicates unit testing of individual components.

Refactor the reconciliation engine to separate concerns into distinct, composable components. Each reconciliation strategy should implement a common interface, allowing the engine to select strategies based on batch type or configuration. The refactoring should also introduce a proper result object that captures detailed reconciliation outcomes rather than returning primitive values.

### Acceptance Criteria

- Mismatch detection logic is extracted into a dedicated comparator class with pluggable tolerance strategies
- Snapshot merging uses a strategy pattern allowing different merge policies (newest-wins, manual-resolution, quorum-based)
- Break counting returns structured results including matched entries, unmatched entries, and match confidence scores
- Drift scoring is decoupled from batch reconciliation and can be applied to any numeric series
- Reconciliation results include detailed breakdowns: total expected, total observed, matched count, break count, and drift metrics
- Age calculation logic is centralized and consistently applied across all reconciliation operations
- Existing reconciliation test assertions pass with the refactored implementation
- Code coverage for reconciliation module exceeds 90%

### Test Command

```bash
bundle exec rspec
```

---

## Task 3: Risk Gate Performance Optimization (Performance Optimization)

### Description

Production metrics indicate that the risk gate module is a bottleneck during high-volume trading periods. The exposure ratio calculations, VaR estimates, and concentration risk assessments are called millions of times per settlement window, and current benchmarks show 45ms p99 latency for risk evaluations.

Optimize the risk gate module to achieve sub-5ms p99 latency without sacrificing accuracy. This may involve caching intermediate calculations, using more efficient data structures for position lookups, pre-computing static thresholds, and batching risk evaluations where possible. The optimization should also reduce memory allocations during hot paths.

### Acceptance Criteria

- Exposure ratio calculations use memoization for repeated collateral lookups within the same evaluation context
- VaR estimation pre-sorts position arrays and reuses sorted results for multiple confidence levels
- Concentration risk assessment uses a max-heap for O(1) maximum position retrieval
- Dynamic buffer calculations cache volatility-based computations for the same volatility score
- Risk tier determination uses a binary search on threshold boundaries instead of sequential comparisons
- Batch risk evaluation amortizes setup costs across multiple positions
- All existing risk gate tests pass with identical results
- Memory allocations in hot paths are reduced by at least 50%

### Test Command

```bash
bundle exec rspec
```

---

## Task 4: Compliance Override API Extension (API Extension)

### Description

The compliance module currently provides basic override validation, but regulatory requirements mandate a more comprehensive override lifecycle. The API needs to be extended to support override requests, approvals, expirations, revocations, and audit trail generation. Additionally, overrides must now specify the exact policy clauses being bypassed and include risk acknowledgments.

The extended API should integrate with the existing audit chain to create tamper-evident records of all override activities. Override approvals must support multi-party authorization with configurable quorum requirements based on override severity.

### Acceptance Criteria

- Override requests include policy clause identifiers, risk acknowledgment signatures, and requested TTL
- Multi-party approval workflow supports configurable quorum (e.g., 2-of-3 approvers for standard, 3-of-5 for critical)
- Override expiration is automatically enforced with configurable grace periods
- Revocation API allows immediate termination of active overrides with mandatory reason codes
- All override lifecycle events are recorded in the audit chain with appropriate fingerprints
- Escalation rules trigger notifications when override requests exceed defined thresholds
- Override queries support filtering by status, policy clause, requestor, and time range
- Backward compatibility maintained for existing override_allowed? consumers

### Test Command

```bash
bundle exec rspec
```

---

## Task 5: Ledger Window to Time-Series Store Migration (Migration)

### Description

ClearLedger's ledger window module currently uses in-memory bucketing for event windowing, which limits horizontal scalability and causes data loss on process restarts. The platform needs to migrate to a time-series storage backend while maintaining the same windowing semantics and query patterns.

The migration should introduce an abstraction layer that supports both the legacy in-memory implementation and the new time-series backend. This allows gradual rollout with feature flags and provides a fallback path. The migration must handle backfilling historical data and ensure consistency during the dual-write period.

### Acceptance Criteria

- Storage abstraction interface defines bucket_for, watermark_accept?, lag_seconds, window_range, and event_in_window? operations
- In-memory implementation of the abstraction passes all existing ledger window tests
- Time-series implementation supports configurable retention policies per bucket type
- Dual-write mode writes to both backends and compares results, logging discrepancies
- Backfill utility populates time-series store from existing event logs with progress tracking
- Window merge operations work correctly across storage backends
- Staleness scoring queries the appropriate backend based on event age
- Compaction triggers based on entry count thresholds in both storage backends

### Test Command

```bash
bundle exec rspec
```
