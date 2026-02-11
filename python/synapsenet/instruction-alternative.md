# SynapseNet - Alternative Tasks

## Overview

This task set focuses on five alternative engineering challenges in the SynapseNet ML/AI platform: real-time feature freshness monitoring, model lifecycle consolidation, batch inference optimization, hyperparameter comparison capabilities, and distributed training migration.

## Environment

- **Language**: Python (FastAPI/Django/Celery)
- **Infrastructure**: Kafka, PostgreSQL x4, Redis, Consul, MinIO, Elasticsearch
- **Difficulty**: Distinguished Engineer (24-48 hours)

## Tasks

### Task 1: Real-Time Feature Freshness Monitoring (Feature Development)

Implement a comprehensive feature freshness monitoring system that tracks the age of features in the online store, detects online/offline consistency violations, and exposes these metrics through the monitoring service. The system must integrate with the existing feature store architecture without impacting serving latency, support configurable SLAs per feature group, and generate alerts when freshness thresholds are exceeded.

### Task 2: Consolidate Model Lifecycle Management (Refactoring)

Refactor the model lifecycle management scattered across three services (models, registry, inference) into a unified state machine pattern. Implement proper saga pattern for handling failures during multi-step operations and ensure all state transitions are validated and published to Kafka. The refactoring must maintain external API compatibility while simplifying internal service communication.

### Task 3: Optimize Batch Inference Throughput (Performance Optimization)

Optimize the batch inference pipeline to maximize throughput while maintaining latency SLAs. This includes implementing adaptive batching that adjusts batch sizes based on current load, parallel batch processing using thread pools, and intelligent cache management with frequency-based eviction. The optimization must improve throughput by at least 2x while maintaining deterministic predictions and graceful degradation under load.

### Task 4: Hyperparameter Comparison API (API Extension)

Extend the experiments service with rich hyperparameter comparison capabilities. Implement new endpoints for querying experiments by hyperparameter ranges, computing statistical significance between experiment pairs, identifying best-performing configurations, and generating importance rankings. Support both point-in-time and trajectory comparisons, handle varying hyperparameter schemas gracefully, and maintain acceptable query performance for comparing up to 100 experiments.

### Task 5: Migrate Distributed Training to Async SGD (Migration)

Implement a migration path from synchronous to asynchronous distributed training using a parameter server architecture with bounded staleness. The async system should allow fast workers to proceed without waiting while ensuring convergence through proper stale gradient handling and dynamic learning rate adjustment. Migration must be backward compatible, allowing existing sync jobs to continue while new jobs can opt into async mode with worker elasticity support.

## Getting Started

```bash
# Start all services
docker compose up -d

# Run tests (will fail initially)
docker compose -f docker-compose.test.yml up --build

# Or run tests directly
python -m pytest tests/ -v
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
