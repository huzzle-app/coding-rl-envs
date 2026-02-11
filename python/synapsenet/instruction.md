# SynapseNet - AI/ML Model Serving & Training Platform

## Architecture

The platform consists of 15 microservices:

| Service | Technology | Port | Database |
|---------|-----------|------|----------|
| Gateway | FastAPI | 8000 | - |
| Auth | Django | 8001 | users_db |
| Models | FastAPI | 8002 | models_db |
| Registry | Django | 8003 | models_db |
| Training | Celery/FastAPI | 8004 | models_db |
| Inference | FastAPI | 8005 | - |
| Features | Django | 8006 | models_db |
| Pipeline | Celery/FastAPI | 8007 | models_db |
| Experiments | Django | 8008 | experiments_db |
| Monitoring | FastAPI | 8009 | metrics_db |
| Scheduler | Django | 8010 | models_db |
| Workers | Celery | 8011 | - |
| Storage | FastAPI | 8012 | models_db |
| Webhooks | Django | 8013 | models_db |
| Admin | Django | 8014 | users_db |

### Infrastructure Components

- **Kafka** (Zookeeper) - Event bus on port 9092
- **PostgreSQL** x4 - models_db (5432), users_db (5433), experiments_db (5434), metrics_db (5435)
- **Redis 7** - Caching, distributed locks on port 6379
- **Consul 1.16** - Service discovery on port 8500
- **MinIO** - Model artifact storage on ports 9000/9001
- **Elasticsearch 8** - Model/experiment search on port 9200

## Getting Started

```bash
# Start all services
docker compose up -d

# Run tests (will fail initially)
docker compose -f docker-compose.test.yml up --build

# Or run tests directly
python -m pytest tests/ -v
```

## Known Issues

The test suite has multiple failures. Main issues appear to be in the core business logic and infrastructure layers.

## Key Challenges

### 1. Setup Hell

The services won't even start initially. You must fix these issues first:
- Circular imports between shared ML and client modules
- Missing Kafka topics (auto.create.topics.enable is disabled)
- Elasticsearch index mappings not created
- MinIO bucket creation fails silently
- Service dependency order (services start before dependencies are ready)
- Version conflicts in requirements.txt

### 2. ML-Specific Debugging

Bugs involve ML concepts:
- Gradient accumulation overflow with large batch sizes
- Batch normalization statistics leaking between training and inference
- Feature drift detection producing false positives on correlated features
- Mixed-precision NaN propagation with certain architectures
- Checkpoint corruption under concurrent save operations

### 3. 15-Service Complexity

Bugs span multiple services. Operations involve cross-service communication through Kafka events, HTTP calls, and shared storage.

### 4. Bug Dependencies (Depth 7+)

Some bugs depend on others being fixed first:
- Diamond: B1 depends on [A1, M1, L5]
- Cross-category: I3 depends on B1 (deserialization needs serving)

### 5. Subtle ML Bugs

Many bugs only manifest under specific conditions:
- Race conditions requiring concurrent model deployments
- Floating-point precision bugs in feature computations
- Timezone bugs in experiment timestamp comparisons
- Data-dependent failures with specific feature distributions

## Common Bug Patterns

- **Float vs Decimal**: Feature values and metrics using `float` instead of `Decimal`
- **Missing Locks**: Concurrent model deployments without proper locking
- **Timezone-naive**: `datetime.now()` without timezone awareness
- **Off-by-one**: Learning rate scheduler steps, batch indexing
- **Pickle Unsafe**: Model serialization using pickle instead of safe formats
- **Race Conditions**: Model swap during inference, feature cache updates
- **Memory Leaks**: Model loading without proper cleanup

## Test Categories

| Category | Tests | Weight | Description |
|----------|-------|--------|-------------|
| Unit (ML Pipeline) | 150 | 1.0x | ML pipeline function tests |
| Unit (Model Serving) | 100 | 1.0x | Model serving tests |
| Unit (Feature Store) | 80 | 1.0x | Feature store tests |
| Unit (Experiments) | 70 | 1.0x | Experiment tracking tests |
| Integration | 100 | 1.5x | Cross-service tests |
| Chaos (Distributed) | 60 | 3.0x | Distributed training failure tests |
| Chaos (Serving) | 40 | 3.0x | Model serving failure tests |
| Security | 60 | 2.5x | Vulnerability tests |
| Performance | 40 | 2.0x | Latency/throughput tests |
| Contract | 30 | 2.0x | API contract verification |
| System | 30 | 3.0x | End-to-end scenarios |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/__init__.py` - circular import chain
2. **L4**: Kafka `auto.create.topics.enable` is disabled
3. **L5**: Services start before dependencies are ready
4. **L9**: MinIO bucket creation fails silently
5. **L10**: Celery broker URL wrong protocol

### Key Files to Examine

| Service | File | Bugs |
|---------|------|------|
| shared | `ml/model_loader.py` | M1, M2, M8, B1, I3 |
| shared | `ml/feature_utils.py` | C1, C2, C3, C4 |
| shared | `clients/base.py` | G1, G3, H6 |
| shared | `utils/distributed.py` | A1, A2, A9, F10 |
| training | `main.py` | A1, A2, A3, M2, M5, M8 |
| inference | `main.py` | B1, B2, B3, B5, B7, B9, H1 |
| features | `views.py` | C1, C2, C5, C6, C7, C8 |
| experiments | `views.py` | E1, E2, E3, E4, E5, E8 |

## Success Criteria

- All tests pass
- Services start without errors
- No security vulnerabilities detected
- Performance tests complete within timeout
- All services achieve isolation (tests for each service pass independently)

## Reward Function

The environment uses sparse rewards with 8 thresholds:

```
Pass Rate -> Reward
< 10% -> 0.00
10-25% -> 0.05
25-40% -> 0.12
40-55% -> 0.22
55-70% -> 0.38
70-85% -> 0.55
85-95% -> 0.78
100% -> 1.00
```

Additional bonuses:
- **Service isolation**: +0.02 per fully passing service
- **ML pipeline tests**: +0.10 for passing ML-specific tests
- **Regression penalty**: -0.15 for re-breaking tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Feature freshness monitoring, model lifecycle consolidation, batch inference optimization, hyperparameter comparison API, async SGD migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Model A/B Testing service, training data versioning system, model explainability engine |

These tasks test different software engineering skills while using the same codebase.
