# TensorForge - Greenfield Implementation Tasks

## Overview

TensorForge supports 3 greenfield implementation tasks that require building new modules from scratch while following existing architectural patterns. These tasks test module design, trait-based abstraction, and integration with the existing platform.

## Environment

- **Language**: Rust (edition 2021)
- **Infrastructure**: PostgreSQL 15, Redis 7 (Docker Compose)
- **Difficulty**: Apex-Principal
- **Codebase**: 14 source modules with established patterns for concurrency, data structures, and error handling

## Tasks

### Task 1: Model Registry Service (Greenfield Implementation)

Implement a model registry service that tracks ML model versions, deployment states, and metadata. The registry supports model lifecycle management, version comparison, and deployment coordination across the TensorForge platform.

Create `src/registry.rs` with version control (semantic versioning), deployment state machine (Registered → Validating → Staging → Canary → Production → Deprecated → Archived), model metadata storage, and validation result tracking.

**Key Responsibilities**:
- Model version parsing, formatting, and comparison
- State transition validation according to the deployment lifecycle
- Shape compatibility scoring for model compatibility assessment
- Model selection algorithm (highest accuracy, lowest p99 latency)
- Rollback priority scoring
- Thread-safe registry using RwLock for read-heavy, write-light access

**Integration Points**:
- Use `statistics::percentile` for latency calculations
- Follow `security::TokenStore` pattern for thread-safe storage
- Follow `workflow::can_transition` pattern for state machine logic

**Test Command**: `cargo test registry`

### Task 2: GPU Memory Allocator (Greenfield Implementation)

Implement a GPU memory allocation service that manages tensor memory pools, tracks allocations, handles fragmentation, and provides memory pressure metrics. This module coordinates with the existing allocator for capacity planning.

Create `src/gpu_memory.rs` with memory block management, best-fit allocation strategy, block merging/splitting, LRU eviction policy for cached blocks, and defragmentation support.

**Key Responsibilities**:
- Alignment calculations (power-of-2 alignment for GPU memory)
- Best-fit allocation with block splitting
- Fragmentation ratio calculation
- Memory pressure estimation
- Eviction of cached blocks using LRU ordering
- Defragmentation for compacting allocated blocks
- Thread-safe pool operations using Mutex

**Integration Points**:
- Integrate with `allocator::check_capacity` for capacity validation
- Use `queue::queue_pressure` pattern for memory pressure calculation
- Follow `allocator::RollingWindowScheduler` pattern for thread-safe state
- Support pinned blocks (cannot be evicted) and cached blocks (evictable)

**Test Command**: `cargo test gpu_memory`

### Task 3: Training Checkpoint Manager (Greenfield Implementation)

Implement a checkpoint manager for ML training state persistence. The manager handles checkpoint creation, restoration, garbage collection, and distributed training coordination. Integrates with the resilience module for fault tolerance.

Create `src/checkpoint.rs` with checkpoint lifecycle management, incremental checkpoint chaining (via parent_id), restoration chain building, and garbage collection policies.

**Key Responsibilities**:
- Checkpoint creation and completion lifecycle
- Checkpoint state transitions (Creating → Complete/Corrupted → Deleted)
- Checkpoint type support (Full, Incremental, Emergency)
- Parent-child chaining for incremental checkpoints
- Restoration chain building (root to target in order)
- Chain length and size calculations
- Garbage collection based on policy (max age, keep-best-N)
- Selection scoring based on restore criteria
- Thread-safe operations using RwLock

**Integration Points**:
- Use `resilience::Checkpoint` pattern for checkpoint structure
- Integrate with `resilience::CheckpointManager::should_checkpoint` for interval logic
- Use `workflow::shortest_path` pattern for chain traversal
- Follow `events::deduplicate` pattern for ID-based operations
- Support metric-based checkpoint selection ("best" checkpoints)

**Test Command**: `cargo test checkpoint`

## Getting Started

```bash
# Start Docker dependencies
docker compose up -d

# Read existing module patterns
# - src/allocator.rs for memory/resource management patterns
# - src/resilience.rs for fault tolerance integration
# - src/statistics.rs for metrics and calculations
# - src/workflow.rs for state machine patterns

# Run tests (most will initially fail due to missing implementations)
cargo test

# Run tests for a specific module
cargo test registry
cargo test gpu_memory
cargo test checkpoint
```

## Success Criteria

All specified implementations must:

1. **Implement all trait methods** with correct logic per specifications
2. **Handle edge cases** (alignment calculations, empty pools, null checks)
3. **Maintain thread safety** using appropriate locking primitives
4. **Follow existing patterns** for error handling, data structures, and tests
5. **Include comprehensive tests** covering normal cases, edge cases, and concurrent scenarios
6. **Preserve integration points** with existing modules

Implementation is validated by passing all test cases: minimum 20 tests for registry, minimum 25 tests for gpu_memory, minimum 25 tests for checkpoint.
