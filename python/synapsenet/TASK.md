# SynapseNet - AI/ML Model Serving & Training Platform Debug Challenge

## Objective

You are debugging a distributed AI/ML platform with **15 microservices**. The platform has **120 intentional bugs** that cause tests to fail. Your goal is to identify and fix all bugs to achieve **100% test pass rate**.

**Difficulty Level**: Distinguished Engineer (24-48 hours expected)

## Getting Started

```bash
# Start all services
docker compose up -d

# Run tests (will fail initially)
docker compose -f docker-compose.test.yml up --build

# Or run tests directly
python -m pytest tests/ -v
```

## Architecture

```
synapsenet/
├── services/
│ ├── gateway/ # API Gateway (FastAPI) - Port 8000
│ ├── auth/ # Authentication & RBAC (Django) - Port 8001
│ ├── models/ # Model CRUD & Metadata (FastAPI) - Port 8002
│ ├── registry/ # Model Version Registry (Django) - Port 8003
│ ├── training/ # Training Job Orchestration (Celery/FastAPI) - Port 8004
│ ├── inference/ # Model Serving & Predictions (FastAPI) - Port 8005
│ ├── features/ # Feature Store & Serving (Django) - Port 8006
│ ├── pipeline/ # Data Pipeline Orchestration (Celery/FastAPI) - Port 8007
│ ├── experiments/ # Experiment Tracking (Django) - Port 8008
│ ├── monitoring/ # Model Monitoring & Drift (FastAPI) - Port 8009
│ ├── scheduler/ # Job Scheduling & Cron (Django) - Port 8010
│ ├── workers/ # Distributed Task Workers (Celery) - Port 8011
│ ├── storage/ # Artifact & Dataset Storage (FastAPI) - Port 8012
│ ├── webhooks/ # Event Webhooks & Notifications (Django) - Port 8013
│ └── admin/ # Admin Dashboard & Tenants (Django) - Port 8014
├── shared/ # Shared modules (events, clients, utils, ml)
├── tests/ # 750+ tests
└── environment/ # RL environment wrapper
```

## Infrastructure

- **Kafka** (Zookeeper) - Event bus on port 9092
- **PostgreSQL** x4 - models_db (5432), users_db (5433), experiments_db (5434), metrics_db (5435)
- **Redis 7** - Caching, distributed locks on port 6379
- **Consul 1.16** - Service discovery on port 8500
- **MinIO** - Model artifact storage on port 9000/9001
- **Elasticsearch 8** - Model/experiment search on port 9200

## Known Issues

Tests are failing in several areas. Previous maintainer noted problems with async operations and data handling.

## Key Challenges

1. **Setup Hell**: The services won't even start initially. You must fix circular imports, missing Kafka topics, Elasticsearch mappings, MinIO bucket creation, and 10 other setup issues first.

2. **ML-Specific Debugging**: Bugs involve ML concepts like gradient accumulation, batch normalization, feature drift, model versioning, and checkpoint management.

3. **15-Service Complexity**: Bugs span multiple services. Fixing a bug in the training service may require fixes in the registry, storage, and workers services first.

4. **Deep Dependency Chains**: Bug dependency chains go up to depth 7:
 - Diamond: B1 depends on [A1, M1, L5]

5. **Subtle ML Bugs**: Many bugs only manifest under specific conditions:
 - Mixed-precision NaN propagation only with certain model architectures
 - Feature drift false positives only with correlated features
 - Gradient accumulation overflow only with large batch sizes
 - Checkpoint corruption only under concurrent save operations

## Test Categories

| Category | Tests | Weight |
| Unit (ML Pipeline) | 150 | 1.0x |
| Unit (Model Serving) | 100 | 1.0x |
| Unit (Feature Store) | 80 | 1.0x |
| Unit (Experiment Tracking) | 70 | 1.0x |
| Integration | 100 | 1.5x |
| Chaos (Distributed Training) | 60 | 3.0x |
| Chaos (Model Serving) | 40 | 3.0x |
| Security | 60 | 2.5x |
| Performance | 40 | 2.0x |
| Contract | 30 | 2.0x |
| System | 30 | 3.0x |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/__init__.py` - circular import chain between ml and clients
2. **L2**: Check `shared/ml/model_loader.py` - missing import guard for optional dependency
3. **L3**: Database migrations reference non-existent tables
4. **L4**: Kafka `auto.create.topics.enable` is disabled
5. **L5**: Services start before dependencies are ready
6. **L6**: Consul not registered properly
7. **L7**: Redis cluster mode config wrong
8. **L8**: Elasticsearch index mapping missing
9. **L9**: MinIO bucket creation fails silently
10. **L10**: Celery broker URL uses wrong protocol
11. **L11**: CORS misconfiguration blocks cross-service calls
12. **L12**: Logging config uses wrong handler class
13. **L13**: Schema validation init fails on circular reference
14. **L14**: Feature store bootstrap needs training service
15. **L15**: Worker registration needs scheduler service

### Common Bug Patterns

- **Float vs Decimal**: Feature values and metrics using `float` instead of `Decimal`
- **Missing Locks**: Concurrent model deployments without proper locking
- **Timezone-naive**: `datetime.now()` without timezone for experiment timestamps
- **Off-by-one**: Learning rate scheduler step counts, batch indexing
- **Pickle Unsafe**: Model serialization using pickle instead of safe formats
- **Race Conditions**: Model swap during inference, feature cache updates
- **Memory Leaks**: Model loading without proper cleanup

### Key Files to Examine

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that simulate production incidents. These describe **symptoms only** - use them to guide your investigation:

| Scenario | Type | Description |
| `01_model_memory_crisis.md` | PagerDuty Incident | Inference service memory growing unbounded after model deployments |
| `02_training_reproducibility.md` | Slack Discussion | Same seed produces different training results, data not shuffled |
| `03_feature_drift_storm.md` | Alert Flood | 247 drift alerts from correlated features, cycle detection broken |
| `04_ab_test_disaster.md` | Jira Ticket | A/B test traffic split drifting due to float precision, missing warmup |
| `05_distributed_training_hang.md` | Incident Report | Cluster deadlock from lock ordering, parameter server races |

These scenarios connect to bugs across multiple categories:
- **Scenario 1**: B1 (memory leak), H1 (cache eviction)
- **Scenario 2**: M5 (no shuffle), M9 (seed ignored), E3 (seed propagation)
- **Scenario 3**: C3 (float threshold), M4 (correlation), C8 (cycle detection)
- **Scenario 4**: B3 (float precision), B5 (no warmup), B7 (schema drift)
- **Scenario 5**: A1 (param server race), A2 (deadlock), A9 (staleness), F10 (lock ordering)

## Success Criteria

- All 750+ tests pass
- Services start without errors
- No security vulnerabilities detected
- Performance tests complete within timeout
- All services achieve isolation (tests for each service pass independently)
- ML pipeline tests validate numerical correctness
- Distributed training tests pass under simulated failures

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
- Service isolation: +0.02 per fully passing service (max +0.30)
- ML pipeline tests: +0.10 for passing ML-specific tests
- Regression penalty: -0.15 for re-breaking tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Feature freshness monitoring, model lifecycle consolidation, batch inference optimization, hyperparameter comparison API, async SGD migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Model A/B Testing service, training data versioning system, model explainability engine |

These tasks test different software engineering skills while using the same codebase.
