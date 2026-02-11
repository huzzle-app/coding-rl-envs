# NexusTrade - Distributed Trading Platform

## Architecture

The platform consists of 10 microservices:

| Service | Technology | Port | Database |
|---------|-----------|------|----------|
| Gateway | FastAPI | 8000 | - |
| Auth | Django | 8001 | users_db |
| Users | Django | 8002 | users_db |
| Orders | Django | 8003 | orders_db |
| Matching | Python/Redis | 8004 | Redis |
| Risk | Django | 8005 | orders_db |
| Settlement | Django | 8006 | orders_db |
| Market Data | FastAPI | 8007 | - |
| Notifications | Celery | 8008 | - |
| Audit | Django | 8009 | audit_db |

### Infrastructure Components

- **Kafka** (Zookeeper) - Event bus on port 9092
- **PostgreSQL** x3 - orders_db (5432), users_db (5433), audit_db (5434)
- **Redis** - Caching and matching engine on port 6379
- **Consul** - Service discovery on port 8500

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

Tests are failing across several modules. Previous maintainer mentioned problems with async operations and data handling.

## Key Challenges

### 1. Setup Hell

The services won't even start initially. You must fix these issues first:
- Circular imports in shared modules
- Missing Kafka topics (auto.create.topics.enable is disabled)
- Service dependency order (services start before dependencies are ready)
- Version conflicts in requirements.txt

### 2. Multi-Service Debugging

Bugs span multiple services. Fixing one bug may reveal bugs in other services. Many operations involve cross-service communication through Kafka events or HTTP calls.

### 3. Bug Dependencies

Some bugs depend on others being fixed first:
- Event ordering (B1) requires split-brain (A1) fixed
- Token refresh race (E2) requires claims propagation (E1) fixed
- Settlement saga bugs require transaction isolation fixes

### 4. Subtle Bugs

Many bugs only manifest under specific conditions:
- Race conditions requiring concurrent requests
- Floating-point precision bugs accumulating over time
- Timezone bugs appearing around DST transitions
- Data-dependent failures with specific input patterns

## Common Bug Patterns

- **Float vs Decimal**: Trading calculations using `float` instead of `Decimal`
- **Missing Locks**: Concurrent operations without proper locking
- **Timezone-naive**: `datetime.now()` without timezone awareness
- **Off-by-one**: Boundary condition checks using `>=` vs `>`
- **Early Return**: Timing attacks due to different response times
- **Missing Idempotency**: Event handlers processing duplicate events
- **Stale Data**: Cache not invalidated after updates

## Test Categories

| Category | Tests | Weight | Description |
|----------|-------|--------|-------------|
| Unit | 149 | 1.0x | Individual function tests |
| Integration | 143 | 1.5x | Cross-service tests |
| Contract | 50 | 2.0x | API contract verification |
| Chaos | 40 | 3.0x | Failure injection tests |
| Security | 60 | 2.5x | Vulnerability tests |
| Performance | 40 | 2.0x | Latency/throughput tests |
| System | 49 | 3.0x | End-to-end scenarios |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/__init__.py` - circular import chain
2. **L4**: Kafka `auto.create.topics.enable` is disabled
3. **L5**: Services start before dependencies are ready
4. **L9**: Check `requirements.txt` for version conflicts

### Key Files to Examine

| Service | File | Bugs |
|---------|------|------|
| shared | `clients/base.py` | C1, C2, H2 |
| shared | `utils/distributed.py` | A3, D10 |
| shared | `utils/time.py` | F5, F8, I4 |
| auth | `views.py` | E1, E2, E3, E5, I7, I8 |
| orders | `views.py` | A3, B2, D4, D6, F3, F7, I1 |
| matching | `main.py` | A1, B1, B8, F1, F2, F4, F5 |
| risk | `views.py` | G1, G2, G3, G4, G6 |

## Success Criteria

- All tests pass
- Services start without errors
- No security vulnerabilities detected
- Performance tests complete within timeout
- All services achieve isolation (tests for each service pass independently)

## Reward Function

The environment uses sparse rewards with 8 thresholds:

```
Pass Rate → Reward
< 10% → 0.00
10-25% → 0.05
25-40% → 0.12
40-55% → 0.22
55-70% → 0.38
70-85% → 0.55
85-95% → 0.78
100% → 1.00
```

Additional bonuses:
- **Service isolation**: +0.02 per fully passing service
- **Chaos tests**: +0.10 for passing chaos tests
- **Regression penalty**: -0.15 for re-breaking tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | OCO orders, Decimal precision, Snapshot caching, FIX gateway, TimescaleDB migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Market Surveillance Engine, Portfolio Analytics, Smart Order Router |

These tasks test different software engineering skills while using the same codebase.
