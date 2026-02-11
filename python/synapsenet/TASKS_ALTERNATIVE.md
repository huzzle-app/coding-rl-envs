# SynapseNet Alternative Tasks

These are alternative task specifications for the SynapseNet ML/AI training platform. Each task focuses on a different aspect of software engineering work beyond debugging.

---

## Task 1: Real-Time Feature Freshness Monitoring (Feature Development)

### Description

The SynapseNet feature store currently lacks visibility into feature freshness, which is critical for production ML systems. Stale features can silently degrade model accuracy, and the platform has no way to detect when feature pipelines fall behind or when the online/offline feature stores diverge beyond acceptable thresholds.

Implement a comprehensive feature freshness monitoring system that tracks the age of features in the online store, detects online/offline consistency violations, and exposes these metrics through the monitoring service. The system should support configurable freshness SLAs per feature group and generate alerts when features exceed their staleness thresholds.

The monitoring system must integrate with the existing feature store architecture without impacting feature serving latency. It should track freshness at both the feature group level and individual entity level, supporting the use case where some entities receive feature updates more frequently than others.

### Acceptance Criteria

- Feature freshness is tracked with millisecond precision for all feature groups
- Each feature group can define a custom freshness SLA (e.g., "features must be no older than 5 minutes")
- The monitoring service exposes a `/features/freshness` endpoint returning current freshness metrics
- Online/offline consistency checks run periodically and detect divergence above configurable thresholds
- Alerts are generated when feature freshness SLA violations occur
- Freshness metrics are available per entity, not just per feature group aggregate
- The feature serving hot path has no additional latency from freshness tracking
- All existing tests continue to pass

### Test Command

```bash
python -m pytest tests/ -v -k "feature" --tb=short
```

---

## Task 2: Consolidate Model Lifecycle Management (Refactoring)

### Description

Model lifecycle operations are currently scattered across three services: the models service handles CRUD operations, the registry service manages versioning, and the inference service handles deployment. This fragmentation leads to inconsistent state when operations fail mid-way, makes it difficult to implement atomic model deployments, and creates tight coupling between services that should be independent.

Refactor the model lifecycle management to use a unified state machine pattern. All model state transitions (created, training, validating, registered, deploying, serving, deprecated, archived) should flow through a single coordinator that ensures consistency. The coordinator should use the saga pattern to handle failures during multi-step operations like deployments.

The refactoring should not change any external API contracts. Internal service communication should be simplified, and the new architecture should make it straightforward to add new lifecycle states or transition rules in the future.

### Acceptance Criteria

- Model lifecycle states are defined in a single location with clear transition rules
- All state transitions are validated against allowed transitions before execution
- Failed multi-step operations (like deployment) are automatically rolled back using saga compensation
- The models, registry, and inference services delegate lifecycle decisions to the coordinator
- External API endpoints maintain backward compatibility
- State transition events are published to Kafka for downstream consumers
- Concurrent lifecycle operations on the same model are properly serialized
- All existing tests continue to pass with improved reliability

### Test Command

```bash
python -m pytest tests/ -v --tb=short
```

---

## Task 3: Optimize Batch Inference Throughput (Performance Optimization)

### Description

The inference service's request batching implementation has significant performance issues. The current batching timeout is misconfigured, batches are processed sequentially rather than leveraging parallel execution, and the model cache eviction strategy does not consider inference priority. Under load, the service achieves only 40% of theoretical throughput.

Optimize the batch inference pipeline to maximize throughput while maintaining latency SLAs. This includes implementing adaptive batching that adjusts batch sizes based on current load, parallel batch processing using a thread pool, and intelligent cache management that prioritizes frequently-accessed models.

The optimization must not sacrifice correctness for performance. Predictions must remain deterministic (same input always produces same output), request ordering within a batch must not affect results, and the system must gracefully degrade under extreme load rather than failing catastrophically.

### Acceptance Criteria

- Batching timeout is configurable and adapts to current request rate
- Batch processing utilizes multiple threads for parallel execution
- Model cache uses frequency-based eviction instead of pure LRU
- Inference throughput improves by at least 2x under load (measured by performance tests)
- P99 latency does not increase by more than 10% during optimization
- Models currently serving requests are never evicted from cache
- Back-pressure is applied when the request queue exceeds configurable limits
- All existing tests continue to pass, including chaos tests

### Test Command

```bash
python -m pytest tests/performance/ tests/chaos/ -v --tb=short
```

---

## Task 4: Hyperparameter Comparison API (API Extension)

### Description

The experiments service tracks hyperparameters for each training run but provides no way to systematically compare hyperparameter configurations across experiments. Data scientists must manually export data and analyze it externally, slowing down the model iteration cycle.

Extend the experiments API to support rich hyperparameter comparison capabilities. This includes querying experiments by hyperparameter ranges, computing statistical significance between experiment pairs, identifying the best-performing hyperparameter configuration for a given metric, and generating hyperparameter importance rankings.

The API should support both point-in-time comparisons (comparing final metrics) and trajectory comparisons (comparing how metrics evolved during training). It must handle experiments with different hyperparameter schemas gracefully, allowing comparison on the subset of shared parameters.

### Acceptance Criteria

- New endpoint `GET /experiments/compare` accepts a list of experiment IDs and returns comparative metrics
- New endpoint `GET /experiments/search` supports filtering by hyperparameter ranges (e.g., `learning_rate>=0.001`)
- Statistical significance (p-value) is computed for metric differences between experiment pairs
- Hyperparameter importance ranking is available via `GET /experiments/{id}/hyperparameter-importance`
- Experiments with different hyperparameter schemas can be compared on shared parameters
- Trajectory comparison shows metric evolution over training steps
- Query performance remains acceptable for comparing up to 100 experiments
- All new endpoints have corresponding tests with >80% coverage

### Test Command

```bash
python -m pytest tests/unit/test_experiment_tracking.py tests/contract/ -v --tb=short
```

---

## Task 5: Migrate Distributed Training to Async SGD (Migration)

### Description

The distributed training system currently uses synchronous gradient all-reduce, where all workers must complete their gradient computation before any can proceed. This causes slow workers to bottleneck the entire training cluster. The platform needs to migrate to asynchronous SGD to improve training throughput and resource utilization.

Implement a migration path from synchronous to asynchronous distributed training. The async system should use a parameter server architecture with bounded staleness to ensure convergence while allowing fast workers to proceed without waiting. The migration must be backward compatible, allowing existing training jobs to continue using sync mode while new jobs can opt into async mode.

The migration should include proper handling of stale gradients, dynamic learning rate adjustment based on staleness, and automatic worker elasticity where workers can join or leave the training cluster without disrupting the job.

### Acceptance Criteria

- Training jobs can specify `mode: sync` or `mode: async` in their configuration
- Async training uses a parameter server with bounded staleness (configurable max staleness)
- Stale gradients beyond the staleness bound are rejected with a clear error
- Learning rate is automatically scaled down based on gradient staleness
- Workers can dynamically join or leave an async training job
- Sync mode continues to work identically to before the migration
- Training convergence with async mode is validated against sync baseline
- All existing distributed training tests pass, with new tests for async mode

### Test Command

```bash
python -m pytest tests/chaos/test_distributed_training.py tests/unit/test_ml_pipeline.py -v --tb=short
```
