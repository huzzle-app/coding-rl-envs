# ClearLedger - Alternative Tasks

## Overview

ClearLedger supports 5 alternative task types that test different software engineering skills: feature development, refactoring, performance optimization, API design, and system migration. Each task uses the same codebase but exercises different aspects of the clearing and settlement platform.

## Environment

- **Language**: Ruby
- **Infrastructure**: 12 services (settlement, reconciliation, risk, compliance, audit, ledger)
- **Difficulty**: Ultra-Principal (8-tier reward threshold)

## Tasks

### Task 1: Multi-Currency Settlement Netting (Feature Development)

Extend the settlement engine to group entries by currency, compute net positions per currency with currency-specific reserve ratios, and apply FX rates at the final settlement stage. The feature must maintain backward compatibility with existing single-currency workflows while enabling cross-currency netting for eligible counterparties.

### Task 2: Reconciliation Engine Refactoring (Refactoring)

Refactor the tightly coupled reconciliation module into composable strategy components. Separate mismatch detection, snapshot merging, break counting, and drift scoring into dedicated classes implementing a common interface. Introduce structured result objects that capture detailed reconciliation outcomes.

### Task 3: Risk Gate Performance Optimization (Performance Optimization)

Optimize the risk gate module to achieve sub-5ms p99 latency (from current 45ms) without sacrificing accuracy. Use memoization for collateral lookups, pre-sorted arrays for VaR, max-heaps for concentration risk, and binary search for tier determination. Target 50%+ memory allocation reduction.

### Task 4: Compliance Override API Extension (API Extension)

Extend the compliance module to support a comprehensive override lifecycle: requests, multi-party approvals, expiration, revocation, and audit trail integration. Overrides must specify policy clauses, risk acknowledgments, and support configurable quorum-based approval workflows.

### Task 5: Ledger Window to Time-Series Store Migration (Migration)

Migrate the ledger window module from in-memory bucketing to a time-series storage backend while maintaining windowing semantics. Introduce an abstraction layer supporting both implementations, enable gradual rollout with feature flags, and implement dual-write validation.

## Getting Started

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
