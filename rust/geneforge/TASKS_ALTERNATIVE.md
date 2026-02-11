# GeneForge - Alternative Tasks

This document describes alternative tasks for the GeneForge clinical genomics analysis platform. Each task represents a realistic development scenario that a bioinformatics engineer might encounter.

---

## Task 1: Feature Development - Variant Annotation Confidence Scoring

### Description

The clinical research team needs a comprehensive variant annotation confidence scoring system to help prioritize findings for review. Currently, variant calling results lack a standardized confidence score that integrates multiple quality signals including read depth, allele balance, mapping quality, and population frequency data.

The new feature should calculate a composite confidence score (0.0-1.0) for each variant annotation by weighting multiple evidence sources. Variants with scores above configurable thresholds should be automatically flagged for priority review, while low-confidence variants should be marked for secondary analysis. The system must handle edge cases such as missing data fields, multi-allelic sites, and variants in repetitive regions where confidence is inherently lower.

Additionally, the scoring algorithm needs to be configurable per assay type (whole genome, exome, targeted panel) since different sequencing approaches have different quality characteristics and acceptable thresholds.

### Acceptance Criteria

- Implement a `VariantConfidenceScorer` struct that accepts quality metrics and returns a normalized score between 0.0 and 1.0
- Support configurable weight parameters for depth, allele balance, mapping quality, and population frequency components
- Handle missing or null values gracefully by falling back to conservative scoring
- Implement assay-specific threshold configurations for WGS, WES, and targeted panel workflows
- Add a `confidence_tier()` function that categorizes variants as "high", "medium", "low", or "insufficient"
- Integrate confidence scores with the existing QC metrics pipeline
- Ensure thread-safe access to configuration parameters for concurrent variant processing
- All existing tests continue to pass with the new functionality

### Test Command

```bash
cargo test
```

---

## Task 2: Refactoring - Cohort Aggregation Pipeline Modularization

### Description

The cohort aggregation module has grown organically and now contains tightly coupled functions that make testing and maintenance difficult. The current implementation mixes data transformation, statistical calculation, and validation logic within single functions, violating separation of concerns principles.

The refactoring should extract distinct responsibilities into well-defined traits and structs: data ingestion/transformation, statistical computation, and result validation. This separation will enable easier unit testing of individual components, allow swapping of statistical backends (e.g., for GPU-accelerated computation in future), and improve code readability for the growing bioinformatics team.

Special attention must be paid to maintaining backward compatibility with existing API consumers while introducing the new internal architecture. All public function signatures should remain stable, with the refactored internals being implementation details.

### Acceptance Criteria

- Extract a `CohortTransformer` trait for data transformation operations with at least three implementations
- Create a `StatisticalEngine` trait abstraction for computation functions (mean, variance, percentile calculations)
- Implement a `ValidationPipeline` that chains multiple validators for cohort data integrity checks
- Refactor `summarize_cohort()` to use the new trait-based architecture without changing its public signature
- Refactor `merge_cohorts()` to support pluggable merge strategies via trait objects
- Add documentation comments explaining the new architecture and extension points
- Reduce cyclomatic complexity of any function currently exceeding 10 to under 8
- All existing tests pass without modification to test code

### Test Command

```bash
cargo test
```

---

## Task 3: Performance Optimization - Batch QC Processing Throughput

### Description

The quality control pipeline is experiencing throughput bottlenecks when processing large sequencing batches (1000+ samples). Profiling has revealed that the current implementation processes samples sequentially and performs redundant calculations when computing batch-level statistics from individual sample metrics.

The optimization effort should focus on three areas: parallelizing independent QC metric calculations across samples using Rayon or similar, implementing incremental/streaming statistics computation to avoid multiple passes over data, and adding memoization for expensive threshold lookups that are repeated across samples in the same batch.

The optimization must maintain numerical precision - the genomics team has strict requirements that QC scores must match the current implementation to 6 decimal places to ensure regulatory compliance and reproducibility of historical analyses.

### Acceptance Criteria

- Implement parallel processing for independent sample QC calculations with configurable thread pool size
- Add streaming/incremental computation for `batch_qc_pass_rate()` that processes samples in a single pass
- Implement a threshold cache to avoid repeated computation of coverage tier boundaries
- Reduce batch processing time by at least 50% for batches of 1000+ samples (as measured by benchmark tests)
- Maintain numerical precision to 6 decimal places for all QC score calculations
- Add `#[inline]` hints and investigate SIMD opportunities for hot path functions
- Ensure thread-safety for all shared state with appropriate synchronization primitives
- All existing tests pass with identical numerical results

### Test Command

```bash
cargo test
```

---

## Task 4: API Extension - Federated Consent Query Protocol

### Description

GeneForge needs to participate in a multi-institution research network that requires federated consent queries. External systems need to verify patient consent status without receiving the underlying consent records, supporting privacy-preserving collaboration across institutional boundaries.

The new API should implement a query protocol where external systems can ask "Does patient X consent to study type Y?" and receive a boolean response along with a cryptographic proof of the query execution. The system must support consent delegation chains (e.g., a parent consenting for a minor) and temporal queries (e.g., "Was consent valid at timestamp T?").

The implementation must be HIPAA-compliant, ensuring that query patterns themselves do not leak information about which patients exist in the system. Rate limiting and audit logging are mandatory for all federated queries.

### Acceptance Criteria

- Implement a `FederatedConsentQuery` struct with fields for subject identifier, study type, and query timestamp
- Create a `FederatedConsentResponse` containing the boolean result, query hash, and response timestamp
- Add support for consent delegation chains with a maximum depth of 3 levels
- Implement temporal consent queries that check validity at a specified historical timestamp
- Add rate limiting (configurable requests per minute per querying institution)
- Generate comprehensive audit log entries for every federated query including source institution
- Implement query anonymization to prevent inference attacks from query patterns
- Extend `can_access_dataset()` to support federated query mode without modifying existing behavior
- All existing consent tests pass unchanged

### Test Command

```bash
cargo test
```

---

## Task 5: Migration - Pipeline Stage State Machine Formalization

### Description

The current pipeline stage management uses ad-hoc conditional logic for state transitions, making it difficult to reason about valid workflow paths and detect invalid state combinations. As the platform scales to support more complex multi-omics workflows, a formal state machine implementation is needed.

The migration should replace the current stage transition logic with a proper finite state machine that explicitly defines valid transitions, guards (conditions that must be true for a transition), and actions (side effects triggered by transitions). The state machine should support workflow variants - some clinical workflows skip certain stages (e.g., annotation-only reanalysis), while research workflows may have additional stages.

The migration must be backward compatible, ensuring that all existing pipeline runs in the database can be mapped to valid states in the new state machine, and that in-flight pipelines complete correctly during the migration window.

### Acceptance Criteria

- Define a `PipelineStateMachine` struct with explicit state and transition definitions
- Implement transition guards as closures that receive pipeline context and return boolean
- Support workflow variants with different valid stage progressions (clinical, research, reanalysis)
- Add transition actions that execute atomically with state changes (e.g., audit logging, metric emission)
- Implement `can_transition()` that validates both state validity and guard conditions
- Create a migration function that validates all existing `PipelineRun` instances against the new state machine
- Add comprehensive error types for invalid transitions with diagnostic information
- Maintain backward compatibility with existing `advance()` and `can_retry()` method signatures
- All existing pipeline tests pass without modification

### Test Command

```bash
cargo test
```
