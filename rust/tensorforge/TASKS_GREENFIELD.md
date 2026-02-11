# TensorForge Greenfield Tasks

This document defines greenfield implementation tasks for extending TensorForge with new modules. Each task requires building a new service/module from scratch while following existing architectural patterns.

## Prerequisites

Before starting any greenfield task:

1. Study the existing module patterns in `src/` (e.g., `allocator.rs`, `workflow.rs`, `resilience.rs`)
2. Understand the data structures in `models.rs` and `contracts.rs`
3. Review the concurrency patterns using `std::sync::Mutex` and `std::sync::RwLock`
4. Familiarize yourself with the test patterns in `tests/`

## Task 1: Model Registry Service

### Overview

Implement a model registry service that tracks ML model versions, deployment states, and metadata. The registry supports model lifecycle management, version comparison, and deployment coordination across the TensorForge platform.

### Trait Contract

Create `src/registry.rs` with the following trait and implementations:

```rust
use std::collections::HashMap;
use std::sync::RwLock;

/// Model version following semantic versioning
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct ModelVersion {
    pub major: u32,
    pub minor: u32,
    pub patch: u32,
}

/// Deployment state of a model
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DeploymentState {
    Registered,
    Validating,
    Staging,
    Canary,
    Production,
    Deprecated,
    Archived,
}

/// Metadata for a registered model
#[derive(Clone, Debug)]
pub struct ModelMetadata {
    pub model_id: String,
    pub name: String,
    pub version: ModelVersion,
    pub framework: String,           // e.g., "pytorch", "tensorflow", "onnx"
    pub input_shape: Vec<usize>,
    pub output_shape: Vec<usize>,
    pub size_bytes: u64,
    pub checksum: String,
    pub registered_at: u64,
    pub state: DeploymentState,
    pub tags: HashMap<String, String>,
}

/// Result of a model validation check
#[derive(Clone, Debug)]
pub struct ValidationResult {
    pub model_id: String,
    pub version: ModelVersion,
    pub passed: bool,
    pub latency_p50_ms: f64,
    pub latency_p99_ms: f64,
    pub accuracy_score: f64,
    pub errors: Vec<String>,
}

/// Compare two model versions
/// Returns: -1 if a < b, 0 if a == b, 1 if a > b
pub fn compare_versions(a: &ModelVersion, b: &ModelVersion) -> i32;

/// Parse a version string "major.minor.patch" into ModelVersion
/// Returns None if parsing fails
pub fn parse_version(version_str: &str) -> Option<ModelVersion>;

/// Format a ModelVersion as "major.minor.patch" string
pub fn format_version(version: &ModelVersion) -> String;

/// Check if a state transition is valid in the deployment lifecycle
/// Valid transitions:
///   Registered -> Validating
///   Validating -> Staging | Registered (on failure)
///   Staging -> Canary | Registered (on failure)
///   Canary -> Production | Staging (on rollback)
///   Production -> Deprecated
///   Deprecated -> Archived
pub fn can_transition_state(from: &DeploymentState, to: &DeploymentState) -> bool;

/// Calculate model compatibility score based on shape matching
/// Returns 1.0 for exact match, 0.0-1.0 for partial compatibility
pub fn shape_compatibility(input_a: &[usize], output_a: &[usize],
                           input_b: &[usize], output_b: &[usize]) -> f64;

/// Determine if a model meets minimum validation thresholds
/// Requirements: latency_p99 <= max_latency_ms, accuracy >= min_accuracy
pub fn meets_sla(result: &ValidationResult, max_latency_ms: f64, min_accuracy: f64) -> bool;

/// Select the best model version from candidates based on:
/// - Must be in Production or Canary state
/// - Highest accuracy score
/// - Lowest p99 latency as tiebreaker
pub fn select_best_model(candidates: &[(ModelMetadata, ValidationResult)]) -> Option<String>;

/// Calculate rollback priority score
/// Higher score = more urgent rollback needed
/// Factors: error count, latency degradation, accuracy drop
pub fn rollback_priority(current: &ValidationResult, baseline: &ValidationResult) -> f64;

/// Thread-safe model registry
pub struct ModelRegistry {
    models: RwLock<HashMap<String, Vec<ModelMetadata>>>,
    validations: RwLock<HashMap<(String, ModelVersion), ValidationResult>>,
}

impl ModelRegistry {
    /// Create a new empty registry
    pub fn new() -> Self;

    /// Register a new model version
    /// Returns error if version already exists for this model_id
    pub fn register(&self, metadata: ModelMetadata) -> Result<(), String>;

    /// Get metadata for a specific model version
    pub fn get(&self, model_id: &str, version: &ModelVersion) -> Option<ModelMetadata>;

    /// Get the latest version of a model (by version number)
    pub fn get_latest(&self, model_id: &str) -> Option<ModelMetadata>;

    /// List all versions for a model
    pub fn list_versions(&self, model_id: &str) -> Vec<ModelVersion>;

    /// Update deployment state for a model version
    pub fn transition_state(&self, model_id: &str, version: &ModelVersion,
                           new_state: DeploymentState) -> Result<(), String>;

    /// Record validation results for a model version
    pub fn record_validation(&self, result: ValidationResult);

    /// Get validation results for a model version
    pub fn get_validation(&self, model_id: &str, version: &ModelVersion) -> Option<ValidationResult>;

    /// Find all models in a given deployment state
    pub fn find_by_state(&self, state: DeploymentState) -> Vec<ModelMetadata>;

    /// Count total registered models (unique model_ids)
    pub fn model_count(&self) -> usize;

    /// Count total model versions across all models
    pub fn version_count(&self) -> usize;
}
```

### Required Integration Points

1. Add `pub mod registry;` to `src/lib.rs`
2. Use `statistics::percentile` for latency calculations in validation
3. Use `workflow::can_transition` pattern for state machine logic
4. Follow `security::TokenStore` pattern for thread-safe storage

### Acceptance Criteria

- [ ] All trait methods implemented with correct logic
- [ ] State transitions follow the defined lifecycle exactly
- [ ] Version comparison handles edge cases (0.0.0, max values)
- [ ] Thread-safe operations using RwLock appropriately
- [ ] Unit tests covering:
  - Version parsing and comparison (edge cases)
  - All valid and invalid state transitions
  - Shape compatibility scoring
  - Model selection algorithm
  - Registry CRUD operations
  - Concurrent access patterns
- [ ] Test command: `cargo test registry`
- [ ] Minimum 20 test cases

---

## Task 2: GPU Memory Allocator

### Overview

Implement a GPU memory allocation service that manages tensor memory pools, tracks allocations, handles fragmentation, and provides memory pressure metrics. This module coordinates with the existing allocator for capacity planning.

### Trait Contract

Create `src/gpu_memory.rs` with the following:

```rust
use std::collections::HashMap;
use std::sync::Mutex;

/// Memory block status
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BlockStatus {
    Free,
    Allocated,
    Pinned,      // Cannot be evicted
    Cached,      // Can be evicted if needed
}

/// A contiguous memory block
#[derive(Clone, Debug)]
pub struct MemoryBlock {
    pub block_id: String,
    pub offset: usize,
    pub size: usize,
    pub status: BlockStatus,
    pub tensor_id: Option<String>,
    pub allocated_at: u64,
    pub last_accessed: u64,
}

/// GPU device information
#[derive(Clone, Debug)]
pub struct GpuDevice {
    pub device_id: String,
    pub total_memory: usize,
    pub memory_clock_mhz: u32,
    pub compute_capability: (u32, u32),  // e.g., (8, 6) for SM 8.6
}

/// Allocation request
#[derive(Clone, Debug)]
pub struct AllocationRequest {
    pub tensor_id: String,
    pub size: usize,
    pub alignment: usize,        // Must be power of 2
    pub pinned: bool,
    pub priority: i32,           // Higher = more important
}

/// Allocation result
#[derive(Clone, Debug)]
pub struct AllocationResult {
    pub success: bool,
    pub block_id: Option<String>,
    pub offset: Option<usize>,
    pub actual_size: Option<usize>,
    pub error: Option<String>,
}

/// Memory pool statistics
#[derive(Clone, Debug)]
pub struct PoolStats {
    pub total_bytes: usize,
    pub allocated_bytes: usize,
    pub free_bytes: usize,
    pub pinned_bytes: usize,
    pub cached_bytes: usize,
    pub fragmentation_ratio: f64,
    pub largest_free_block: usize,
    pub block_count: usize,
    pub allocation_count: usize,
}

/// Align a size up to the given alignment (alignment must be power of 2)
pub fn align_up(size: usize, alignment: usize) -> usize;

/// Check if a value is a power of 2
pub fn is_power_of_two(n: usize) -> bool;

/// Calculate fragmentation ratio: 1.0 - (largest_free / total_free)
/// Returns 0.0 if no free memory, 1.0 if completely fragmented
pub fn fragmentation_ratio(blocks: &[MemoryBlock]) -> f64;

/// Find the best-fit free block for an allocation
/// Returns the block_id of the smallest free block that fits
pub fn best_fit_block(blocks: &[MemoryBlock], size: usize, alignment: usize) -> Option<String>;

/// Find blocks eligible for eviction (Cached status, sorted by last_accessed ascending)
pub fn eviction_candidates(blocks: &[MemoryBlock]) -> Vec<String>;

/// Calculate memory pressure: allocated / total, clamped to [0.0, 1.0]
pub fn memory_pressure(allocated: usize, total: usize) -> f64;

/// Determine if defragmentation is needed
/// Triggers when: fragmentation > threshold AND largest_free < min_block_size
pub fn should_defragment(stats: &PoolStats, frag_threshold: f64, min_block_size: usize) -> bool;

/// Estimate time to OOM based on allocation rate
/// Returns seconds until memory exhaustion at current rate
pub fn estimate_oom_seconds(free_bytes: usize, alloc_rate_bytes_per_sec: f64) -> f64;

/// Calculate optimal pool size for a workload
/// Based on peak usage * headroom_factor, rounded up to page_size
pub fn optimal_pool_size(peak_usage: usize, headroom_factor: f64, page_size: usize) -> usize;

/// GPU memory pool manager
pub struct MemoryPool {
    device: GpuDevice,
    blocks: Mutex<Vec<MemoryBlock>>,
    next_block_id: Mutex<u64>,
}

impl MemoryPool {
    /// Create a new memory pool for a device
    /// Initializes with a single free block spanning total memory
    pub fn new(device: GpuDevice) -> Self;

    /// Allocate memory for a tensor
    /// Uses best-fit strategy, splits blocks as needed
    pub fn allocate(&self, request: AllocationRequest, now: u64) -> AllocationResult;

    /// Free an allocated block
    /// Merges with adjacent free blocks if possible
    pub fn free(&self, block_id: &str) -> Result<(), String>;

    /// Mark a block as cached (evictable)
    pub fn mark_cached(&self, block_id: &str) -> Result<(), String>;

    /// Pin a block (prevent eviction)
    pub fn pin(&self, block_id: &str) -> Result<(), String>;

    /// Unpin a block
    pub fn unpin(&self, block_id: &str) -> Result<(), String>;

    /// Update last accessed time for a block
    pub fn touch(&self, block_id: &str, now: u64) -> Result<(), String>;

    /// Evict cached blocks to free at least `needed` bytes
    /// Returns total bytes freed
    pub fn evict(&self, needed: usize) -> usize;

    /// Defragment the pool by compacting allocated blocks
    /// Returns number of blocks moved
    pub fn defragment(&self) -> usize;

    /// Get current pool statistics
    pub fn stats(&self) -> PoolStats;

    /// Get block by ID
    pub fn get_block(&self, block_id: &str) -> Option<MemoryBlock>;

    /// List all blocks for a tensor
    pub fn blocks_for_tensor(&self, tensor_id: &str) -> Vec<MemoryBlock>;
}
```

### Required Integration Points

1. Add `pub mod gpu_memory;` to `src/lib.rs`
2. Integrate with `allocator::check_capacity` for capacity validation
3. Use `queue::queue_pressure` pattern for memory pressure calculation
4. Follow `allocator::RollingWindowScheduler` pattern for thread-safe state

### Acceptance Criteria

- [ ] All trait methods implemented with correct logic
- [ ] Alignment calculations handle edge cases (0, 1, non-power-of-2)
- [ ] Block splitting and merging work correctly
- [ ] Eviction respects pinned status and uses LRU ordering
- [ ] Defragmentation preserves allocation semantics
- [ ] Thread-safe operations using Mutex appropriately
- [ ] Unit tests covering:
  - Alignment calculations (power of 2 edge cases)
  - Best-fit allocation strategy
  - Block splitting and merging
  - Eviction ordering (LRU)
  - Fragmentation calculation
  - Concurrent allocations
  - Edge cases (full pool, single block, etc.)
- [ ] Test command: `cargo test gpu_memory`
- [ ] Minimum 25 test cases

---

## Task 3: Training Checkpoint Manager

### Overview

Implement a checkpoint manager for ML training state persistence. The manager handles checkpoint creation, restoration, garbage collection, and distributed training coordination. Integrates with the resilience module for fault tolerance.

### Trait Contract

Create `src/checkpoint.rs` with the following:

```rust
use std::collections::HashMap;
use std::sync::RwLock;

/// Checkpoint state
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CheckpointState {
    Creating,
    Complete,
    Corrupted,
    Deleted,
}

/// Type of checkpoint
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CheckpointType {
    Full,           // Complete model state
    Incremental,    // Delta from previous checkpoint
    Emergency,      // Created on failure detection
}

/// Checkpoint metadata
#[derive(Clone, Debug)]
pub struct CheckpointMeta {
    pub checkpoint_id: String,
    pub training_run_id: String,
    pub epoch: u32,
    pub step: u64,
    pub checkpoint_type: CheckpointType,
    pub state: CheckpointState,
    pub size_bytes: u64,
    pub created_at: u64,
    pub parent_id: Option<String>,    // For incremental checkpoints
    pub metrics: HashMap<String, f64>, // loss, accuracy, etc.
    pub storage_path: String,
}

/// Checkpoint creation request
#[derive(Clone, Debug)]
pub struct CreateCheckpointRequest {
    pub training_run_id: String,
    pub epoch: u32,
    pub step: u64,
    pub checkpoint_type: CheckpointType,
    pub metrics: HashMap<String, f64>,
}

/// Restore point selection criteria
#[derive(Clone, Debug)]
pub struct RestoreCriteria {
    pub training_run_id: String,
    pub max_epoch: Option<u32>,
    pub max_step: Option<u64>,
    pub require_complete: bool,
    pub prefer_full: bool,           // Prefer full over incremental
}

/// Garbage collection policy
#[derive(Clone, Debug)]
pub struct GcPolicy {
    pub max_checkpoints_per_run: usize,
    pub max_age_seconds: u64,
    pub keep_best_n: usize,          // Keep N checkpoints with best metrics
    pub metric_key: String,          // Metric to use for "best" (e.g., "loss")
    pub metric_ascending: bool,       // true = lower is better
}

/// Calculate checkpoint chain length from a checkpoint to root
/// Follows parent_id links until None
pub fn chain_length(checkpoints: &[CheckpointMeta], checkpoint_id: &str) -> usize;

/// Find the root checkpoint in a chain (the one with no parent)
pub fn find_chain_root(checkpoints: &[CheckpointMeta], checkpoint_id: &str) -> Option<String>;

/// Build the full restoration chain from root to target
/// Returns checkpoint IDs in order they should be applied
pub fn restoration_chain(checkpoints: &[CheckpointMeta], target_id: &str) -> Vec<String>;

/// Calculate total size of a checkpoint chain
pub fn chain_size(checkpoints: &[CheckpointMeta], target_id: &str) -> u64;

/// Determine if a checkpoint is eligible for garbage collection
/// Based on age, position in chain (not latest), and policy
pub fn is_gc_eligible(checkpoint: &CheckpointMeta, policy: &GcPolicy,
                      latest_step: u64, now: u64, is_best: bool) -> bool;

/// Score a checkpoint for selection (higher = better match for criteria)
/// Factors: completeness, type preference, recency, chain length
pub fn selection_score(checkpoint: &CheckpointMeta, criteria: &RestoreCriteria) -> f64;

/// Estimate restoration time based on checkpoint chain
/// Base time + per-checkpoint overhead + size-based transfer time
pub fn estimate_restore_time(chain: &[CheckpointMeta], base_ms: u64,
                             per_checkpoint_ms: u64, bytes_per_ms: f64) -> u64;

/// Validate checkpoint integrity
/// Checks: non-empty path, valid epoch/step progression, consistent parent chain
pub fn validate_checkpoint(checkpoint: &CheckpointMeta,
                          all_checkpoints: &[CheckpointMeta]) -> Result<(), String>;

/// Thread-safe checkpoint manager
pub struct CheckpointManager {
    checkpoints: RwLock<HashMap<String, CheckpointMeta>>,
    run_checkpoints: RwLock<HashMap<String, Vec<String>>>,  // run_id -> checkpoint_ids
    gc_policy: GcPolicy,
    next_id: RwLock<u64>,
}

impl CheckpointManager {
    /// Create a new checkpoint manager with the given GC policy
    pub fn new(gc_policy: GcPolicy) -> Self;

    /// Create a new checkpoint
    /// Generates unique ID, sets state to Creating
    pub fn create(&self, request: CreateCheckpointRequest, now: u64) -> CheckpointMeta;

    /// Mark a checkpoint as complete with final size and storage path
    pub fn complete(&self, checkpoint_id: &str, size_bytes: u64,
                   storage_path: String) -> Result<(), String>;

    /// Mark a checkpoint as corrupted
    pub fn mark_corrupted(&self, checkpoint_id: &str) -> Result<(), String>;

    /// Get checkpoint by ID
    pub fn get(&self, checkpoint_id: &str) -> Option<CheckpointMeta>;

    /// Find the best checkpoint matching restore criteria
    pub fn find_restore_point(&self, criteria: &RestoreCriteria) -> Option<CheckpointMeta>;

    /// List all checkpoints for a training run
    pub fn list_for_run(&self, training_run_id: &str) -> Vec<CheckpointMeta>;

    /// Get the latest checkpoint for a training run
    pub fn get_latest(&self, training_run_id: &str) -> Option<CheckpointMeta>;

    /// Run garbage collection, returns IDs of deleted checkpoints
    pub fn gc(&self, now: u64) -> Vec<String>;

    /// Get total checkpoint count across all runs
    pub fn total_count(&self) -> usize;

    /// Get total storage used across all checkpoints
    pub fn total_size(&self) -> u64;

    /// Delete a specific checkpoint
    pub fn delete(&self, checkpoint_id: &str) -> Result<(), String>;

    /// Find checkpoints with metrics better than threshold
    pub fn find_by_metric(&self, training_run_id: &str, metric_key: &str,
                          threshold: f64, ascending: bool) -> Vec<CheckpointMeta>;
}
```

### Required Integration Points

1. Add `pub mod checkpoint;` to `src/lib.rs`
2. Use `resilience::Checkpoint` pattern for checkpoint structure
3. Integrate with `resilience::CheckpointManager::should_checkpoint` for interval logic
4. Use `workflow::shortest_path` pattern for chain traversal
5. Follow `events::deduplicate` pattern for ID-based operations

### Acceptance Criteria

- [ ] All trait methods implemented with correct logic
- [ ] Checkpoint chains correctly linked via parent_id
- [ ] Restoration chain built in correct order (root to target)
- [ ] GC respects "keep best N" and maximum age policies
- [ ] Incremental checkpoints depend on parent existence
- [ ] Thread-safe operations using RwLock appropriately
- [ ] Unit tests covering:
  - Checkpoint creation and completion lifecycle
  - Chain building and traversal
  - Restoration chain ordering
  - GC eligibility rules
  - Selection scoring algorithm
  - Metric-based filtering
  - Concurrent operations
  - Edge cases (empty runs, corrupted parents, etc.)
- [ ] Test command: `cargo test checkpoint`
- [ ] Minimum 25 test cases

---

## General Guidelines

### Code Style

Follow the existing TensorForge patterns:

1. Use `std::sync::Mutex` for mutable state with simple access patterns
2. Use `std::sync::RwLock` for read-heavy, write-light access patterns
3. Return `Result<T, String>` for fallible operations
4. Use descriptive error messages that include context
5. Document public functions with `///` doc comments
6. Use `#[derive(Clone, Debug)]` for data structures

### Testing Patterns

Follow the test structure in `tests/core_tests.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_function_name_scenario() {
        // Arrange
        let input = ...;

        // Act
        let result = function_name(input);

        // Assert
        assert_eq!(result, expected);
    }
}
```

### Running Tests

```bash
# Run all tests
cargo test

# Run tests for a specific module
cargo test registry
cargo test gpu_memory
cargo test checkpoint

# Run with output
cargo test -- --nocapture
```
