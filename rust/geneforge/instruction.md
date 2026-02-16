# GeneForge - Distributed Clinical Genomics Analysis Platform

**Language:** Rust
**Difficulty:** Principal
**Bugs:** 136
**Tests:** 1200+

## Overview

Fix bugs across a clinical genomics analysis platform. The codebase handles sequence ingestion, alignment orchestration, variant calling pipelines, cohort aggregation, phenotype correlation, and compliance-safe reporting.

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run tests
cargo test

# Run full verification
bash tests/test.sh
```

## Source Files

Key modules in `src/`:
- `pipeline.rs` - Genomics workflow stage orchestration
- `qc.rs` - Quality control metrics and thresholds
- `consent.rs` - Patient consent validation
- `statistics.rs` - Variant quality and statistical functions
- `resilience.rs` - Circuit breaker and backoff logic
- `reporting.rs` - Clinical report generation
- `aggregator.rs` - Cohort variant aggregation

## Success Criteria

- All tests pass
- Privacy/security suites are fully green
- Final full-suite pass rate reaches 100%

A submission is correct when Harbor writes reward `1.0`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Confidence scoring, pipeline modularization, QC throughput, federated consent, state machine |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Variant caller service, alignment validator, population frequency calculator |

These tasks test different software engineering skills while using the same codebase.
