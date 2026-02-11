# VectorHarbor - Greenfield Tasks

## Overview

These three greenfield tasks require implementing new modules from scratch while following VectorHarbor's architectural patterns. Each module integrates with the existing allocation, routing, security, and statistics infrastructure through defined trait contracts.

## Environment

- **Language**: Rust 2021
- **Infrastructure**: Maritime orchestration platform with existing allocator, routing, policy, queue, security, resilience, statistics, and workflow modules
- **Difficulty**: Hyper-Principal (70-140h, 9200+ tests)

## Tasks

### Task 1: Vector Compression Service

**Module**: `src/compression.rs`

Implement a compression service reducing storage requirements for vessel telemetry vectors while maintaining query accuracy. The service supports three compression algorithms (Scalar Quantization, Product Quantization, Run-Length Encoding) with four quality tiers (Lossless, HighQuality, Balanced, Aggressive). Provide compression/decompression with error bound validation, algorithm recommendation based on vector sparsity, and thread-safe statistics tracking.

**Key Types**:
- `CompressionAlgorithm` enum (ScalarQuantization, ProductQuantization, RunLengthEncoding)
- `QualityTier` enum (Lossless, HighQuality, Balanced, Aggressive)
- `CompressionResult` with data, sizes, ratio, algorithm, and quality
- `DecompressionResult` with reconstructed values and optional error metrics
- `CompressionService` thread-safe struct with Mutex-protected statistics

**Acceptance Criteria**: Minimum 15 unit tests, 80% code coverage, round-trip accuracy verification, thread-safe statistics accumulation.

---

### Task 2: Index Build Orchestrator

**Module**: `src/indexer.rs`

Implement an orchestrator managing the lifecycle of vector index builds across multiple shards. The orchestrator coordinates build phases (Pending → Ingesting → Building → Optimizing → Validating → Completed/Failed/Cancelled), tracks per-shard progress, handles failures with configurable retry logic, and integrates with the policy engine for operational state awareness.

**Key Types**:
- `BuildPhase` enum (Pending, Ingesting, Building, Optimizing, Validating, Completed, Failed, Cancelled)
- `ShardStatus` struct tracking individual shard progress with phase, vectors processed, and retry count
- `BuildJobStatus` struct with aggregate progress across all shards
- `BuildConfig` configuration with max retries, phase timeouts, and parallelism
- `IndexOrchestrator` thread-safe struct with RwLock jobs and Mutex event history

**Acceptance Criteria**: Minimum 20 unit tests, 85% code coverage, phase transition validation, shard progress aggregation, job creation/cancellation, event history recording, policy integration for pause support.

---

### Task 3: Query Result Ranker

**Module**: `src/ranker.rs`

Implement a ranking service scoring and ordering query results based on multiple signals: vector similarity (0.0-1.0), freshness (age-based decay), authority (e.g., page rank), and custom metadata. The service supports pluggable scoring functions with weight-based combination, score normalization, and detailed explanations for debugging.

**Key Types**:
- `RankCandidate` struct with id, similarity, age_secs, authority, and custom metadata
- `RankingWeights` struct with weights for similarity, freshness, authority, and custom signals
- `FreshnessDecay` enum (Linear, Exponential, Step, None) affecting score computation
- `FreshnessConfig` with decay function, max age, half-life, and step threshold
- `ScoreExplanation` with final score and per-signal contribution breakdown
- `RankedResult` with candidate, final score, rank position, and optional explanation
- `RankingService` thread-safe struct with Mutex-protected statistics

**Acceptance Criteria**: Minimum 25 unit tests, 85% code coverage, all freshness decay functions tested, normalization edge cases covered, explanation accuracy verified, weight validation, diversity filtering, statistics accumulation.

## Getting Started

```bash
cargo test
```

## Success Criteria

Each greenfield implementation:
1. Creates required module with all specified structs, enums, and functions
2. Passes minimum test count (15/20/25 respectively)
3. Achieves minimum code coverage (80%/85%/85%)
4. Integrates with existing modules following VectorHarbor patterns (Mutex/RwLock for thread safety, Result/String for error handling)
5. All existing tests continue to pass after module addition

Implementation details available in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
