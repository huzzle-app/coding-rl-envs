# VectorHarbor Greenfield Tasks

These tasks require implementing new modules from scratch while following VectorHarbor's existing architectural patterns. Each module should integrate with the maritime orchestration platform's allocation, routing, and security infrastructure.

## Test Command

```bash
cargo test
```

---

## Task 1: Vector Compression Service

### Overview

Implement a compression service that reduces storage requirements for vessel telemetry vectors while maintaining query accuracy. The service must support multiple compression algorithms, quality tiers, and decompression with bounded error guarantees.

### Module Location

Create `src/compression.rs` and add `pub mod compression;` to `src/lib.rs`.

### Trait Contract

```rust
use std::sync::Mutex;

/// Compression algorithm identifier
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CompressionAlgorithm {
    /// Scalar quantization - fastest, moderate compression
    ScalarQuantization,
    /// Product quantization - slower, high compression
    ProductQuantization,
    /// Run-length encoding for sparse vectors
    RunLengthEncoding,
}

/// Quality tier affecting compression ratio vs accuracy tradeoff
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum QualityTier {
    /// Lossless compression, no accuracy loss
    Lossless,
    /// High quality, max 1% error
    HighQuality,
    /// Balanced, max 5% error
    Balanced,
    /// Aggressive, max 15% error
    Aggressive,
}

/// Result of a compression operation
#[derive(Clone, Debug)]
pub struct CompressionResult {
    /// Compressed byte representation
    pub data: Vec<u8>,
    /// Original size in bytes
    pub original_size: usize,
    /// Compressed size in bytes
    pub compressed_size: usize,
    /// Compression ratio (original / compressed)
    pub ratio: f64,
    /// Algorithm used
    pub algorithm: CompressionAlgorithm,
    /// Quality tier applied
    pub quality: QualityTier,
}

/// Decompression result with error bounds
#[derive(Clone, Debug)]
pub struct DecompressionResult {
    /// Reconstructed vector values
    pub values: Vec<f64>,
    /// Maximum observed error per dimension (if lossy)
    pub max_error: Option<f64>,
    /// Mean squared error (if lossy)
    pub mse: Option<f64>,
}

/// Compression statistics for monitoring
#[derive(Clone, Debug, Default)]
pub struct CompressionStats {
    /// Total vectors compressed
    pub vectors_compressed: u64,
    /// Total bytes before compression
    pub bytes_input: u64,
    /// Total bytes after compression
    pub bytes_output: u64,
    /// Average compression ratio
    pub avg_ratio: f64,
    /// Average compression time in microseconds
    pub avg_compress_us: f64,
}

/// Compress a vector using the specified algorithm and quality tier.
///
/// # Arguments
/// * `values` - Input vector of f64 values
/// * `algorithm` - Compression algorithm to use
/// * `quality` - Quality tier affecting accuracy/size tradeoff
///
/// # Returns
/// CompressionResult containing compressed data and metadata
pub fn compress_vector(
    values: &[f64],
    algorithm: &CompressionAlgorithm,
    quality: &QualityTier,
) -> CompressionResult {
    todo!()
}

/// Decompress a previously compressed vector.
///
/// # Arguments
/// * `data` - Compressed byte data
/// * `algorithm` - Algorithm used during compression
/// * `original_len` - Original vector length
///
/// # Returns
/// DecompressionResult with reconstructed values and error metrics
pub fn decompress_vector(
    data: &[u8],
    algorithm: &CompressionAlgorithm,
    original_len: usize,
) -> DecompressionResult {
    todo!()
}

/// Calculate the maximum allowed error for a quality tier.
///
/// # Arguments
/// * `quality` - The quality tier
///
/// # Returns
/// Maximum allowed relative error as a fraction (0.0 = lossless, 0.15 = 15%)
pub fn max_error_for_quality(quality: &QualityTier) -> f64 {
    todo!()
}

/// Determine the best compression algorithm for a given vector.
///
/// Analyzes vector characteristics (sparsity, value distribution) to
/// select the most effective algorithm.
///
/// # Arguments
/// * `values` - Input vector to analyze
///
/// # Returns
/// Recommended compression algorithm
pub fn recommend_algorithm(values: &[f64]) -> CompressionAlgorithm {
    todo!()
}

/// Calculate sparsity ratio of a vector (fraction of zero/near-zero values).
///
/// # Arguments
/// * `values` - Input vector
/// * `threshold` - Values with abs() below this are considered zero
///
/// # Returns
/// Sparsity ratio between 0.0 (dense) and 1.0 (all zeros)
pub fn calculate_sparsity(values: &[f64], threshold: f64) -> f64 {
    todo!()
}

/// Thread-safe compression service with statistics tracking.
pub struct CompressionService {
    default_algorithm: CompressionAlgorithm,
    default_quality: QualityTier,
    stats: Mutex<CompressionStats>,
}

impl CompressionService {
    /// Create a new compression service with default settings.
    pub fn new(algorithm: CompressionAlgorithm, quality: QualityTier) -> Self {
        todo!()
    }

    /// Compress a vector using service defaults, updating statistics.
    pub fn compress(&self, values: &[f64]) -> CompressionResult {
        todo!()
    }

    /// Compress with explicit algorithm and quality override.
    pub fn compress_with(
        &self,
        values: &[f64],
        algorithm: &CompressionAlgorithm,
        quality: &QualityTier,
    ) -> CompressionResult {
        todo!()
    }

    /// Get current compression statistics.
    pub fn stats(&self) -> CompressionStats {
        todo!()
    }

    /// Reset statistics counters.
    pub fn reset_stats(&self) {
        todo!()
    }
}

/// Validate that decompressed values are within quality tier bounds.
///
/// # Arguments
/// * `original` - Original vector values
/// * `decompressed` - Reconstructed vector values
/// * `quality` - Quality tier to validate against
///
/// # Returns
/// Ok(()) if within bounds, Err with actual max error if exceeded
pub fn validate_quality(
    original: &[f64],
    decompressed: &[f64],
    quality: &QualityTier,
) -> Result<(), f64> {
    todo!()
}
```

### Required Structs/Enums

- `CompressionAlgorithm` - enum with ScalarQuantization, ProductQuantization, RunLengthEncoding
- `QualityTier` - enum with Lossless, HighQuality, Balanced, Aggressive
- `CompressionResult` - struct with data, sizes, ratio, algorithm, quality
- `DecompressionResult` - struct with values and optional error metrics
- `CompressionStats` - struct for monitoring compression performance
- `CompressionService` - thread-safe service with Mutex-protected stats

### Acceptance Criteria

1. **Unit Tests** (minimum 15 test functions):
   - Test each compression algorithm with various vector sizes
   - Test each quality tier's error bounds
   - Test sparsity calculation edge cases
   - Test algorithm recommendation logic
   - Test thread-safe statistics accumulation
   - Test compression/decompression round-trip accuracy

2. **Integration Points**:
   - Statistics should be compatible with `src/statistics.rs` patterns
   - Service should follow `Mutex<>` patterns from existing modules

3. **Code Coverage**: Minimum 80% line coverage for the new module

---

## Task 2: Index Build Orchestrator

### Overview

Implement an orchestrator that manages the lifecycle of vector index builds across multiple shards. The orchestrator coordinates build phases, tracks progress, handles failures with retry logic, and integrates with the existing policy engine for operational state awareness.

### Module Location

Create `src/indexer.rs` and add `pub mod indexer;` to `src/lib.rs`.

### Trait Contract

```rust
use std::collections::HashMap;
use std::sync::{Mutex, RwLock};

/// Index build phase in the lifecycle
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BuildPhase {
    /// Initial state, not yet started
    Pending,
    /// Collecting vectors for indexing
    Ingesting,
    /// Building index structures
    Building,
    /// Optimizing index for queries
    Optimizing,
    /// Validating index integrity
    Validating,
    /// Build completed successfully
    Completed,
    /// Build failed
    Failed,
    /// Build cancelled by user
    Cancelled,
}

/// Shard status within a build job
#[derive(Clone, Debug)]
pub struct ShardStatus {
    /// Shard identifier
    pub shard_id: String,
    /// Current phase
    pub phase: BuildPhase,
    /// Vectors processed so far
    pub vectors_processed: u64,
    /// Total vectors to process
    pub vectors_total: u64,
    /// Progress percentage (0.0 - 100.0)
    pub progress: f64,
    /// Error message if failed
    pub error: Option<String>,
    /// Retry count for this shard
    pub retries: u32,
    /// Last update timestamp (unix millis)
    pub last_update: u64,
}

/// Overall build job status
#[derive(Clone, Debug)]
pub struct BuildJobStatus {
    /// Job identifier
    pub job_id: String,
    /// Aggregate phase (worst phase across shards)
    pub phase: BuildPhase,
    /// Total vectors across all shards
    pub total_vectors: u64,
    /// Processed vectors across all shards
    pub processed_vectors: u64,
    /// Overall progress percentage
    pub progress: f64,
    /// Per-shard status
    pub shards: Vec<ShardStatus>,
    /// Job start time (unix millis)
    pub started_at: u64,
    /// Job completion time if finished
    pub completed_at: Option<u64>,
}

/// Configuration for a build job
#[derive(Clone, Debug)]
pub struct BuildConfig {
    /// Maximum retries per shard before failing job
    pub max_retries: u32,
    /// Timeout per phase in seconds
    pub phase_timeout_secs: u64,
    /// Number of parallel shard builds
    pub parallelism: usize,
    /// Whether to continue on shard failure
    pub continue_on_failure: bool,
}

impl Default for BuildConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            phase_timeout_secs: 3600,
            parallelism: 4,
            continue_on_failure: false,
        }
    }
}

/// Build job event for history tracking
#[derive(Clone, Debug)]
pub struct BuildEvent {
    /// Job identifier
    pub job_id: String,
    /// Shard identifier (None for job-level events)
    pub shard_id: Option<String>,
    /// Event type description
    pub event_type: String,
    /// Previous phase
    pub from_phase: Option<BuildPhase>,
    /// New phase
    pub to_phase: BuildPhase,
    /// Event timestamp
    pub timestamp: u64,
}

/// Check if a phase transition is valid.
///
/// # Arguments
/// * `from` - Current phase
/// * `to` - Target phase
///
/// # Returns
/// true if the transition is allowed
pub fn can_transition_phase(from: &BuildPhase, to: &BuildPhase) -> bool {
    todo!()
}

/// Get the next phase in the normal build sequence.
///
/// # Arguments
/// * `current` - Current phase
///
/// # Returns
/// Next phase, or None if terminal
pub fn next_phase(current: &BuildPhase) -> Option<BuildPhase> {
    todo!()
}

/// Check if a phase is terminal (Completed, Failed, Cancelled).
///
/// # Arguments
/// * `phase` - Phase to check
///
/// # Returns
/// true if no further transitions expected
pub fn is_terminal_phase(phase: &BuildPhase) -> bool {
    todo!()
}

/// Calculate aggregate progress from shard statuses.
///
/// # Arguments
/// * `shards` - Slice of shard statuses
///
/// # Returns
/// Aggregate progress percentage (0.0 - 100.0)
pub fn aggregate_progress(shards: &[ShardStatus]) -> f64 {
    todo!()
}

/// Determine aggregate phase from shard phases (returns worst phase).
///
/// # Arguments
/// * `phases` - Slice of shard phases
///
/// # Returns
/// The "worst" phase representing overall status
pub fn aggregate_phase(phases: &[BuildPhase]) -> BuildPhase {
    todo!()
}

/// Calculate estimated time remaining based on progress rate.
///
/// # Arguments
/// * `progress` - Current progress (0.0 - 100.0)
/// * `elapsed_secs` - Seconds since start
///
/// # Returns
/// Estimated seconds remaining, or None if cannot estimate
pub fn estimate_remaining_secs(progress: f64, elapsed_secs: u64) -> Option<u64> {
    todo!()
}

/// Thread-safe index build orchestrator.
pub struct IndexOrchestrator {
    jobs: RwLock<HashMap<String, BuildJobStatus>>,
    config: BuildConfig,
    events: Mutex<Vec<BuildEvent>>,
}

impl IndexOrchestrator {
    /// Create a new orchestrator with the given configuration.
    pub fn new(config: BuildConfig) -> Self {
        todo!()
    }

    /// Create a new build job with the specified shards.
    ///
    /// # Arguments
    /// * `job_id` - Unique job identifier
    /// * `shard_ids` - List of shard identifiers
    /// * `vectors_per_shard` - Vector count for each shard
    /// * `now` - Current timestamp
    ///
    /// # Returns
    /// Ok(()) on success, Err if job_id already exists
    pub fn create_job(
        &self,
        job_id: &str,
        shard_ids: &[&str],
        vectors_per_shard: &[u64],
        now: u64,
    ) -> Result<(), String> {
        todo!()
    }

    /// Advance a shard to the next phase.
    ///
    /// # Arguments
    /// * `job_id` - Job identifier
    /// * `shard_id` - Shard identifier
    /// * `now` - Current timestamp
    ///
    /// # Returns
    /// New phase on success, Err on invalid transition or not found
    pub fn advance_shard(
        &self,
        job_id: &str,
        shard_id: &str,
        now: u64,
    ) -> Result<BuildPhase, String> {
        todo!()
    }

    /// Report progress for a shard.
    ///
    /// # Arguments
    /// * `job_id` - Job identifier
    /// * `shard_id` - Shard identifier
    /// * `vectors_processed` - Vectors processed so far
    /// * `now` - Current timestamp
    pub fn report_progress(
        &self,
        job_id: &str,
        shard_id: &str,
        vectors_processed: u64,
        now: u64,
    ) -> Result<(), String> {
        todo!()
    }

    /// Mark a shard as failed with error message.
    ///
    /// # Arguments
    /// * `job_id` - Job identifier
    /// * `shard_id` - Shard identifier
    /// * `error` - Error description
    /// * `now` - Current timestamp
    ///
    /// # Returns
    /// true if retry is available, false if max retries exceeded
    pub fn fail_shard(
        &self,
        job_id: &str,
        shard_id: &str,
        error: &str,
        now: u64,
    ) -> Result<bool, String> {
        todo!()
    }

    /// Cancel a build job.
    ///
    /// # Arguments
    /// * `job_id` - Job identifier
    /// * `now` - Current timestamp
    pub fn cancel_job(&self, job_id: &str, now: u64) -> Result<(), String> {
        todo!()
    }

    /// Get current status of a job.
    pub fn get_job(&self, job_id: &str) -> Option<BuildJobStatus> {
        todo!()
    }

    /// List all active (non-terminal) jobs.
    pub fn active_jobs(&self) -> Vec<BuildJobStatus> {
        todo!()
    }

    /// Get event history for a job.
    pub fn job_events(&self, job_id: &str) -> Vec<BuildEvent> {
        todo!()
    }
}

/// Check if orchestrator should pause based on policy state.
///
/// Integrates with the policy module to respect operational mode.
///
/// # Arguments
/// * `policy_state` - Current policy (from policy module)
///
/// # Returns
/// true if builds should be paused
pub fn should_pause_builds(policy_state: &str) -> bool {
    todo!()
}
```

### Required Structs/Enums

- `BuildPhase` - enum with Pending, Ingesting, Building, Optimizing, Validating, Completed, Failed, Cancelled
- `ShardStatus` - struct tracking individual shard progress
- `BuildJobStatus` - struct with aggregate job status
- `BuildConfig` - configuration with retries, timeouts, parallelism
- `BuildEvent` - event record for audit history
- `IndexOrchestrator` - thread-safe orchestrator with RwLock jobs and Mutex events

### Acceptance Criteria

1. **Unit Tests** (minimum 20 test functions):
   - Test phase transition validation (valid and invalid)
   - Test shard progress aggregation
   - Test job creation with various shard counts
   - Test shard advancement through full lifecycle
   - Test failure handling and retry logic
   - Test job cancellation
   - Test event history recording
   - Test policy integration (pause on restricted/halted)

2. **Integration Points**:
   - Use policy states from `src/policy.rs` for `should_pause_builds`
   - Follow workflow patterns from `src/workflow.rs` for state transitions
   - Event history compatible with audit logging patterns

3. **Code Coverage**: Minimum 85% line coverage for the new module

---

## Task 3: Query Result Ranker

### Overview

Implement a ranking service that scores and orders query results based on multiple signals: vector similarity, freshness, authority, and user preferences. The ranker supports pluggable scoring functions, score normalization, and explains ranking decisions for debugging.

### Module Location

Create `src/ranker.rs` and add `pub mod ranker;` to `src/lib.rs`.

### Trait Contract

```rust
use std::collections::HashMap;
use std::sync::Mutex;

/// A single query result candidate for ranking
#[derive(Clone, Debug)]
pub struct RankCandidate {
    /// Unique identifier for the result
    pub id: String,
    /// Raw vector similarity score (0.0 - 1.0)
    pub similarity: f64,
    /// Document/vector age in seconds
    pub age_secs: u64,
    /// Authority score (0.0 - 1.0), e.g., from page rank
    pub authority: f64,
    /// Custom metadata for scoring
    pub metadata: HashMap<String, f64>,
}

/// Scoring weights for ranking signals
#[derive(Clone, Debug)]
pub struct RankingWeights {
    /// Weight for similarity signal
    pub similarity: f64,
    /// Weight for freshness signal
    pub freshness: f64,
    /// Weight for authority signal
    pub authority: f64,
    /// Weights for custom metadata fields
    pub custom: HashMap<String, f64>,
}

impl Default for RankingWeights {
    fn default() -> Self {
        Self {
            similarity: 0.6,
            freshness: 0.2,
            authority: 0.2,
            custom: HashMap::new(),
        }
    }
}

/// Explanation of how a score was computed
#[derive(Clone, Debug)]
pub struct ScoreExplanation {
    /// Final combined score
    pub final_score: f64,
    /// Contribution from similarity
    pub similarity_contribution: f64,
    /// Contribution from freshness
    pub freshness_contribution: f64,
    /// Contribution from authority
    pub authority_contribution: f64,
    /// Contributions from custom signals
    pub custom_contributions: HashMap<String, f64>,
    /// Human-readable breakdown
    pub breakdown: String,
}

/// A ranked result with score and optional explanation
#[derive(Clone, Debug)]
pub struct RankedResult {
    /// Original candidate
    pub candidate: RankCandidate,
    /// Computed final score
    pub score: f64,
    /// Rank position (1-indexed)
    pub rank: usize,
    /// Optional explanation (if requested)
    pub explanation: Option<ScoreExplanation>,
}

/// Freshness decay function type
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum FreshnessDecay {
    /// Linear decay: score = max(0, 1 - age/max_age)
    Linear,
    /// Exponential decay: score = exp(-age/half_life)
    Exponential,
    /// Step function: 1.0 if age < threshold, else 0.0
    Step,
    /// No decay: always 1.0
    None,
}

/// Configuration for freshness scoring
#[derive(Clone, Debug)]
pub struct FreshnessConfig {
    /// Decay function type
    pub decay: FreshnessDecay,
    /// Max age for linear decay (seconds)
    pub max_age_secs: u64,
    /// Half-life for exponential decay (seconds)
    pub half_life_secs: u64,
    /// Threshold for step function (seconds)
    pub step_threshold_secs: u64,
}

impl Default for FreshnessConfig {
    fn default() -> Self {
        Self {
            decay: FreshnessDecay::Exponential,
            max_age_secs: 86400 * 30, // 30 days
            half_life_secs: 86400 * 7, // 7 days
            step_threshold_secs: 86400, // 1 day
        }
    }
}

/// Ranker statistics for monitoring
#[derive(Clone, Debug, Default)]
pub struct RankerStats {
    /// Total queries ranked
    pub queries_ranked: u64,
    /// Total candidates scored
    pub candidates_scored: u64,
    /// Average candidates per query
    pub avg_candidates: f64,
    /// Average ranking latency in microseconds
    pub avg_latency_us: f64,
}

/// Calculate freshness score based on age and config.
///
/// # Arguments
/// * `age_secs` - Age of the document in seconds
/// * `config` - Freshness configuration
///
/// # Returns
/// Freshness score between 0.0 and 1.0
pub fn freshness_score(age_secs: u64, config: &FreshnessConfig) -> f64 {
    todo!()
}

/// Normalize a score to the range [0.0, 1.0].
///
/// # Arguments
/// * `value` - Raw score value
/// * `min_value` - Minimum expected value
/// * `max_value` - Maximum expected value
///
/// # Returns
/// Normalized score clamped to [0.0, 1.0]
pub fn normalize_score(value: f64, min_value: f64, max_value: f64) -> f64 {
    todo!()
}

/// Compute the final score for a candidate.
///
/// # Arguments
/// * `candidate` - The candidate to score
/// * `weights` - Scoring weights
/// * `freshness_config` - Freshness scoring configuration
///
/// # Returns
/// Final weighted score
pub fn compute_score(
    candidate: &RankCandidate,
    weights: &RankingWeights,
    freshness_config: &FreshnessConfig,
) -> f64 {
    todo!()
}

/// Compute score with detailed explanation.
///
/// # Arguments
/// * `candidate` - The candidate to score
/// * `weights` - Scoring weights
/// * `freshness_config` - Freshness scoring configuration
///
/// # Returns
/// ScoreExplanation with breakdown
pub fn explain_score(
    candidate: &RankCandidate,
    weights: &RankingWeights,
    freshness_config: &FreshnessConfig,
) -> ScoreExplanation {
    todo!()
}

/// Rank a list of candidates.
///
/// # Arguments
/// * `candidates` - Candidates to rank
/// * `weights` - Scoring weights
/// * `freshness_config` - Freshness configuration
/// * `limit` - Maximum results to return (0 = all)
/// * `explain` - Whether to include explanations
///
/// # Returns
/// Ranked results in descending score order
pub fn rank_candidates(
    candidates: &[RankCandidate],
    weights: &RankingWeights,
    freshness_config: &FreshnessConfig,
    limit: usize,
    explain: bool,
) -> Vec<RankedResult> {
    todo!()
}

/// Validate that weights sum to approximately 1.0.
///
/// # Arguments
/// * `weights` - Weights to validate
///
/// # Returns
/// Ok(()) if valid, Err with actual sum if not
pub fn validate_weights(weights: &RankingWeights) -> Result<(), f64> {
    todo!()
}

/// Thread-safe ranking service with configurable defaults.
pub struct RankingService {
    weights: RankingWeights,
    freshness_config: FreshnessConfig,
    stats: Mutex<RankerStats>,
}

impl RankingService {
    /// Create a new ranking service with default configuration.
    pub fn new() -> Self {
        todo!()
    }

    /// Create with custom weights and freshness config.
    pub fn with_config(weights: RankingWeights, freshness_config: FreshnessConfig) -> Self {
        todo!()
    }

    /// Rank candidates using service configuration.
    ///
    /// # Arguments
    /// * `candidates` - Candidates to rank
    /// * `limit` - Max results (0 = all)
    ///
    /// # Returns
    /// Ranked results without explanations
    pub fn rank(&self, candidates: &[RankCandidate], limit: usize) -> Vec<RankedResult> {
        todo!()
    }

    /// Rank with explanations for debugging.
    pub fn rank_explained(
        &self,
        candidates: &[RankCandidate],
        limit: usize,
    ) -> Vec<RankedResult> {
        todo!()
    }

    /// Override weights for a single query.
    pub fn rank_with_weights(
        &self,
        candidates: &[RankCandidate],
        weights: &RankingWeights,
        limit: usize,
    ) -> Vec<RankedResult> {
        todo!()
    }

    /// Get current statistics.
    pub fn stats(&self) -> RankerStats {
        todo!()
    }

    /// Reset statistics.
    pub fn reset_stats(&self) {
        todo!()
    }
}

/// Diversity-aware re-ranking to reduce result redundancy.
///
/// # Arguments
/// * `results` - Already ranked results
/// * `diversity_threshold` - Minimum similarity distance between results (0.0-1.0)
/// * `limit` - Maximum results after diversification
///
/// # Returns
/// Diversified results maintaining approximate score order
pub fn diversify_results(
    results: &[RankedResult],
    diversity_threshold: f64,
    limit: usize,
) -> Vec<RankedResult> {
    todo!()
}

/// Combine scores from multiple ranking passes (e.g., first-pass + re-rank).
///
/// # Arguments
/// * `scores` - List of scores from different rankers
/// * `weights` - Weight for each ranker's score
///
/// # Returns
/// Combined weighted score
pub fn combine_scores(scores: &[f64], weights: &[f64]) -> f64 {
    todo!()
}
```

### Required Structs/Enums

- `RankCandidate` - struct with id, similarity, age_secs, authority, metadata
- `RankingWeights` - struct with weights for each signal
- `ScoreExplanation` - struct with contribution breakdown and human-readable text
- `RankedResult` - struct with candidate, score, rank, optional explanation
- `FreshnessDecay` - enum with Linear, Exponential, Step, None
- `FreshnessConfig` - configuration for freshness scoring
- `RankerStats` - statistics for monitoring
- `RankingService` - thread-safe service with Mutex-protected stats

### Acceptance Criteria

1. **Unit Tests** (minimum 25 test functions):
   - Test each freshness decay function
   - Test score normalization edge cases
   - Test score computation with various weight combinations
   - Test explanation generation accuracy
   - Test ranking order correctness
   - Test diversity filtering
   - Test weight validation
   - Test score combination from multiple passes
   - Test statistics accumulation
   - Test limit parameter behavior

2. **Integration Points**:
   - Statistics compatible with `src/statistics.rs` patterns
   - Service follows `Mutex<>` patterns from existing modules
   - Weights validation similar to contract validation in `src/contracts.rs`

3. **Code Coverage**: Minimum 85% line coverage for the new module

---

## General Requirements

### Architectural Patterns to Follow

1. **Thread Safety**: Use `Mutex<>` for mutable internal state, `RwLock<>` for read-heavy state
2. **Pure Functions**: Prefer stateless functions for business logic
3. **Error Handling**: Return `Result<T, String>` for fallible operations
4. **Derive Macros**: Use `#[derive(Clone, Debug)]` on all public types
5. **Documentation**: Doc comments on all public items
6. **Constants**: Use `pub const` for configuration defaults

### Testing Guidelines

1. Place tests in `tests/` directory following existing patterns
2. Use descriptive test function names: `test_<function>_<scenario>`
3. Test edge cases: empty inputs, zero values, boundary conditions
4. Test error paths, not just happy paths
5. Use assertions that provide clear failure messages

### Code Quality

1. Run `cargo fmt` before committing
2. Run `cargo clippy` and address warnings
3. No `unwrap()` in library code except in tests
4. Prefer early returns for error conditions
