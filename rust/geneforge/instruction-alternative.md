# GeneForge - Alternative Tasks

## Overview

GeneForge is a clinical genomics analysis platform with 5 alternative development tasks that test different software engineering skills. Each task involves adding features, refactoring existing code, optimizing performance, extending APIs, or performing complex migrations while maintaining compatibility with the 1168+ existing tests.

## Environment

- **Language:** Rust
- **Infrastructure:** Docker Compose with PostgreSQL and Redis dependencies
- **Difficulty:** Principal
- **Base Tests:** 1168+

## Tasks

### Task 1: Feature Development - Variant Annotation Confidence Scoring (Feature)

Implement a comprehensive variant annotation confidence scoring system that integrates multiple quality signals including read depth, allele balance, mapping quality, and population frequency data to calculate composite confidence scores (0.0-1.0) for each variant annotation. The feature must support configurable thresholds for different assay types (WGS, WES, targeted panel) and handle edge cases such as missing data fields and variants in repetitive regions.

### Task 2: Refactoring - Cohort Aggregation Pipeline Modularization (Refactor)

Refactor the cohort aggregation module to separate tightly coupled functionality into well-defined traits and structs. Extract data transformation, statistical computation, and validation logic into `CohortTransformer`, `StatisticalEngine`, and `ValidationPipeline` abstractions. Maintain backward compatibility with existing API consumers while introducing the new internal architecture and improving code maintainability.

### Task 3: Performance Optimization - Batch QC Processing Throughput (Optimize)

Optimize the quality control pipeline for processing large sequencing batches (1000+ samples). Parallelize independent QC metric calculations using Rayon, implement streaming statistics computation, and add memoization for expensive threshold lookups. Must maintain numerical precision to 6 decimal places for regulatory compliance while reducing batch processing time by at least 50%.

### Task 4: API Extension - Federated Consent Query Protocol (API)

Extend the consent validation system to support federated consent queries across multi-institution research networks. Implement a query protocol that verifies patient consent status with cryptographic proof, support consent delegation chains up to 3 levels deep, enable temporal queries on historical timestamps, and add rate limiting and audit logging while ensuring HIPAA compliance.

### Task 5: Migration - Pipeline Stage State Machine Formalization (Migration)

Formalize the pipeline stage management by replacing ad-hoc conditional logic with a proper finite state machine that explicitly defines valid transitions, guards, and actions. Support workflow variants (clinical, research, reanalysis), ensure backward compatibility with existing pipeline runs in the database, and maintain all in-flight pipeline completion during the migration window.

## Getting Started

Start infrastructure and run tests:

```bash
# Start infrastructure
docker compose up -d

# Run tests
cargo test

# Run full verification
bash harbor/test.sh
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). All 1168+ existing tests continue to pass with new functionality integrated. Harbor verification writes reward `1.0` when all requirements are met.
