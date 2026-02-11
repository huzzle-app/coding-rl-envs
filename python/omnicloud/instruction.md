# OmniCloud - Multi-Cloud Infrastructure Orchestration Platform

## Architecture

The platform consists of 15 microservices:

| Service | Technology | Port | Database |
|---------|-----------|------|----------|
| Gateway | FastAPI | 8000 | - |
| Auth | Django | 8001 | tenants_db |
| Tenants | Django | 8002 | tenants_db |
| Compute | FastAPI | 8003 | infra_db |
| Network | Django | 8004 | infra_db |
| Storage | FastAPI | 8005 | infra_db |
| DNS | Django | 8006 | infra_db |
| LoadBalancer | FastAPI | 8007 | infra_db |
| Secrets | Django | 8008 | infra_db |
| Config | Django | 8009 | infra_db |
| Deploy | Celery/FastAPI | 8010 | infra_db |
| Monitor | FastAPI | 8011 | - |
| Billing | Django | 8012 | billing_db |
| Audit | Django | 8013 | audit_db |
| Compliance | Django | 8014 | audit_db |

### Infrastructure Components

- **Kafka** (Zookeeper) - Event bus on port 9092
- **PostgreSQL** x4 - infra_db (5432), tenants_db (5433), billing_db (5434), audit_db (5435)
- **Redis 7** - Caching, distributed locks, pub/sub on port 6379
- **Consul 1.16** - Service discovery, KV store on port 8500
- **etcd 3.5** - Distributed consensus, leader election on port 2379
- **HashiCorp Vault 1.15** - Secret management on port 8200
- **MinIO** - Terraform state storage, artifacts on port 9000

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

## Key Challenges

### 1. Setup Hell

The services will not start initially. You must fix these issues first:
- Circular imports in shared modules
- Missing Kafka topics (auto.create.topics.enable is disabled)
- etcd connection string uses wrong scheme
- Vault auto-unseal not configured
- Service dependency order (services start before dependencies are ready)
- Version conflicts in requirements.txt

### 2. Multi-Service Debugging

Bugs span 15 services. Fixing one bug may reveal bugs in other services. Infrastructure state management touches compute, network, storage, and deploy simultaneously.

### 3. Bug Dependencies (depth 8)

Some bugs have chains requiring up to 8 sequential fixes:

### 4. Diamond Dependencies

Multiple bugs depend on two or more bugs that share ancestors:
- A1 depends on [L5, L6]; B1 depends on [A1, A9]
- F1 depends on [A1, L5, C1]; I3 depends on [G1, C1]

### 5. Subtle Infrastructure Bugs

Many bugs manifest only under specific conditions:
- Race conditions during concurrent resource provisioning
- Floating-point precision in billing calculations
- Eventual consistency violations during partition events
- State machine transition bugs during concurrent modifications

## Common Bug Patterns

- **Float vs Decimal**: Billing calculations using `float` instead of `Decimal`
- **Missing Locks**: Concurrent operations without proper distributed locking
- **Timezone-naive**: `datetime.now()` without timezone awareness
- **Off-by-one**: Boundary conditions in CIDR allocation and batch sizes
- **Early Return**: Timing attacks due to different response times
- **Missing Idempotency**: Event handlers processing duplicate events
- **Stale State**: Cache not invalidated after state transitions

## Test Categories

| Category | Tests | Weight | Description |
|----------|-------|--------|-------------|
| Unit | 200 | 1.0x | Individual function tests |
| Integration | 150 | 1.5x | Cross-service tests |
| Contract | 60 | 2.0x | API contract verification |
| Chaos | 80 | 3.0x | Failure injection tests |
| Security | 80 | 2.5x | Vulnerability tests |
| Performance | 60 | 2.0x | Latency/throughput tests |
| System | 120 | 3.0x | End-to-end scenarios |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/__init__.py` - circular import chain
2. **L3**: Kafka `auto.create.topics.enable` is disabled
3. **L5**: Services start before dependencies are ready
4. **L7**: etcd connection uses wrong scheme
5. **L12**: Check `requirements.txt` for version conflicts

### Key Files to Examine

| Service | File | Bugs |
|---------|------|------|
| shared | `infra/state.py` | A1, A2, A4, A9 |
| shared | `utils/distributed.py` | B1, B3, B4, G10 |
| tenants | `models.py` | C1, C2, C3, C4, C5 |
| network | `views.py` | D1, D2, D3, D4, D5 |
| deploy | `tasks.py` | F1, F2, F3, F4, F5 |
| billing | `views.py` | H1, H2, H3, H4, H5 |

## Success Criteria

- All tests pass
- Services start without errors
- No security vulnerabilities detected
- Performance tests complete within timeout
- All services achieve isolation
- Multi-tenancy isolation verified
- Infrastructure state consistency verified

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
- **Service isolation**: +0.015 per fully passing service
- **Chaos tests**: +0.10 for passing chaos tests
- **Infrastructure state**: +0.05 for passing state management tests
- **Regression penalty**: -0.20 for re-breaking tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-region failover, state reconciliation refactor, scheduler optimization, webhook API, currency migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Cost Allocation Service, Infrastructure Drift Detector, Capacity Forecasting Engine |

These tasks test different software engineering skills while using the same codebase.
