# OmniCloud - Multi-Cloud Infrastructure Orchestration Platform Debug Challenge

## Objective

You are debugging a multi-cloud infrastructure orchestration platform with **15 microservices**. The platform has **120 intentional bugs** that cause tests to fail. Your goal is to identify and fix all bugs to achieve **100% test pass rate**.

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
omnicloud/
├── services/
│ ├── gateway/ # API Gateway (FastAPI) - Port 8000
│ ├── auth/ # Authentication & RBAC (Django) - Port 8001
│ ├── tenants/ # Tenant Management (Django) - Port 8002
│ ├── compute/ # Compute Provisioning (FastAPI) - Port 8003
│ ├── network/ # Network Management (Django) - Port 8004
│ ├── storage/ # Storage Provisioning (FastAPI) - Port 8005
│ ├── dns/ # DNS Management (Django) - Port 8006
│ ├── loadbalancer/ # Load Balancer Provisioning (FastAPI) - Port 8007
│ ├── secrets/ # Secret Management (Django) - Port 8008
│ ├── config/ # Infrastructure Config (Django) - Port 8009
│ ├── deploy/ # Deployment Pipeline (Celery/FastAPI) - Port 8010
│ ├── monitor/ # Monitoring & Alerting (FastAPI) - Port 8011
│ ├── billing/ # Billing & Metering (Django) - Port 8012
│ ├── audit/ # Audit Trail (Django) - Port 8013
│ └── compliance/ # Policy Enforcement (Django) - Port 8014
├── shared/ # Shared modules (events, clients, utils, infra)
├── tests/ # 750+ tests
└── environment/ # RL environment wrapper
```

## Infrastructure

- **Kafka** (Zookeeper) - Event bus on port 9092
- **PostgreSQL** x4 - infra_db (5432), tenants_db (5433), billing_db (5434), audit_db (5435)
- **Redis 7** - Caching, distributed locks, pub/sub on port 6379
- **Consul 1.16** - Service discovery, KV store on port 8500
- **etcd 3.5** - Distributed consensus, leader election on port 2379
- **HashiCorp Vault 1.15** - Secret management on port 8200
- **MinIO** - Terraform state storage, artifacts on port 9000

## Known Issues

The test suite has multiple failures across core modules. Issues appear to span business logic and infrastructure layers.

## Key Challenges

1. **Setup Hell**: The services will not start initially. You must fix circular imports, missing Kafka topics, etcd connection issues, Vault unsealing, and service dependency issues first.

2. **Multi-Service Debugging**: Bugs span 15 services. Fixing one bug may reveal bugs in other services. Infrastructure state management touches compute, network, storage, and deploy simultaneously.

3. **Bug Dependency Chains (depth 8)**: Some bugs have chains requiring 8 sequential fixes. For example:

4. **Diamond Dependencies**: Multiple bugs depend on two or more bugs that share ancestors:
 - A1 depends on [L5, L6]; B1 depends on [A1, A9]
 - F1 depends on [A1, L5, C1]; D1 depends on [C1, L4]
 - I3 depends on [G1, C1]; H1 depends on [A1, G1]

5. **Subtle Infrastructure Bugs**: Many bugs manifest only under specific conditions:
 - Race conditions during concurrent resource provisioning
 - Floating-point precision in billing calculations
 - Eventual consistency violations during partition events
 - State machine transition bugs during concurrent modifications

## Test Categories

| Category | Tests | Weight |
| Unit | 200 | 1.0x |
| Integration | 150 | 1.5x |
| Contract | 60 | 2.0x |
| Chaos | 80 | 3.0x |
| Security | 80 | 2.5x |
| Performance | 60 | 2.0x |
| System | 120 | 3.0x |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/__init__.py` - circular import chain between infra and clients
2. **L2**: Missing migration files in tenants service
3. **L3**: Kafka `auto.create.topics.enable` is disabled
4. **L4**: Database migration ordering between services is wrong
5. **L5**: Services start before dependencies are ready (no healthcheck on gateway)
6. **L6**: Consul ACL bootstrap not completed
7. **L7**: etcd connection string uses wrong scheme (https vs http)
8. **L8**: Vault auto-unseal not configured
9. **L9**: MinIO bucket creation race condition
10. **L10**: Celery broker URL uses wrong Redis database
11. **L11**: CORS middleware misconfigured (blocks inter-service calls)
12. **L12**: Schema validation library version conflict
13. **L13**: Consul service registration missing health check URL
14. **L14**: Worker registration uses wrong serializer
15. **L15**: Environment variable type parsing (string "false" treated as truthy)

### Common Bug Patterns

- **Float vs Decimal**: Billing and resource limit calculations use `float` instead of `Decimal`
- **Missing Locks**: Concurrent state modifications without proper distributed locking
- **Timezone-naive**: `datetime.now()` without timezone awareness in billing
- **Off-by-one**: Boundary conditions in CIDR allocation and batch sizes
- **Early Return**: Timing attacks on API key validation
- **Stale State**: Eventual consistency issues between services
- **Missing Idempotency**: Event handlers processing duplicate infrastructure events

### Key Files to Examine

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that describe symptoms observed in production. These provide context for understanding how the bugs manifest in real-world operations:

| Scenario | Description | Primary Bugs |
| [Billing Discrepancies](scenarios/scenario_01_billing_discrepancies.md) | Customer invoice errors, proration precision loss, duplicate invoices |
| [Deployment Failures](scenarios/scenario_02_deployment_failures.md) | Canary promotes too fast, rolling updates overshoot, lock theft |
| [Network Connectivity](scenarios/scenario_03_network_connectivity.md) | CIDR overlap, VPN MTU drops, firewall rule ordering |
| [Resource Scheduling](scenarios/scenario_04_resource_scheduling.md) | Float precision overcommit, anti-affinity races, tenant isolation |
| [Distributed Consensus](scenarios/scenario_05_distributed_consensus.md) | Split-brain, lock TTL, quorum off-by-one, state corruption |

Use these scenarios to understand the business impact and user-facing symptoms of the bugs you're fixing.

## Success Criteria

- All 750+ tests pass
- Services start without errors
- No security vulnerabilities detected
- Performance tests complete within timeout
- All services achieve isolation (tests for each service pass independently)
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
- Service isolation: +0.015 per fully passing service (15 services)
- Chaos tests: +0.10 for passing chaos tests
- Infrastructure state bonus: +0.05 for passing state management tests
- Regression penalty: -0.20 for re-breaking tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-region failover, state reconciliation refactor, scheduler optimization, webhook API, currency migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Cost Allocation Service, Infrastructure Drift Detector, Capacity Forecasting Engine |

These tasks test different software engineering skills while using the same codebase.
