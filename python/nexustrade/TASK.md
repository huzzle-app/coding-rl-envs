# NexusTrade - Distributed Trading Platform Debug Challenge

## Objective

You are debugging a distributed trading platform with **10 microservices**. The platform has **90 intentional bugs** that cause tests to fail. Your goal is to identify and fix all bugs to achieve **100% test pass rate**.

**Difficulty Level**: Principal/Staff Engineer (8-16 hours expected)

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
nexustrade/
├── services/
│ ├── gateway/ # API Gateway (FastAPI) - Port 8000
│ ├── auth/ # Authentication (Django) - Port 8001
│ ├── users/ # User Management (Django) - Port 8002
│ ├── orders/ # Order Service (Django) - Port 8003
│ ├── matching/ # Matching Engine (Python/Redis) - Port 8004
│ ├── risk/ # Risk Management (Django) - Port 8005
│ ├── settlement/ # Settlement (Django) - Port 8006
│ ├── market-data/ # Market Data Feed (FastAPI) - Port 8007
│ ├── notifications/ # Notifications (Celery) - Port 8008
│ └── audit/ # Audit Logging (Django) - Port 8009
├── shared/ # Shared modules (events, clients, utils)
├── tests/ # 780+ tests
└── environment/ # RL environment wrapper
```

## Infrastructure

- **Kafka** (Zookeeper) - Event bus on port 9092
- **PostgreSQL** x3 - orders_db (5432), users_db (5433), audit_db (5434)
- **Redis** - Caching on port 6379
- **Consul** - Service discovery on port 8500

## Known Issues

Current state: most tests broken. Main concerns include API endpoints, background processing, and database operations.

## Key Challenges

1. **Setup Hell**: The services won't even start initially. You must fix circular imports, missing Kafka topics, and service dependency issues first.

2. **Multi-Service Debugging**: Bugs span multiple services. Fixing one bug may reveal bugs in other services.

3. **Cascading Failures**: Some bugs depend on others being fixed first. For example:
 - Event ordering (B1) requires split-brain (A1) fixed
 - Token refresh race (E2) requires claims propagation (E1) fixed

4. **Subtle Bugs**: Many bugs only manifest under specific conditions:
 - Race conditions that require concurrent requests
 - Floating-point precision bugs that accumulate over time
 - Timezone bugs that only appear around DST transitions

## Test Categories

| Category | Tests | Weight |
| Unit | 149 | 1.0x |
| Integration | 143 | 1.5x |
| Contract | 50 | 2.0x |
| Chaos | 40 | 3.0x |
| Security | 60 | 2.5x |
| Performance | 40 | 2.0x |
| System | 49 | 3.0x |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/__init__.py` - circular import chain
2. **L4**: Kafka `auto.create.topics.enable` is disabled
3. **L5**: Services start before dependencies are ready
4. **L9**: Check `requirements.txt` for version conflicts

### Common Bug Patterns

- **Float vs Decimal**: Many trading calculations use `float` instead of `Decimal`
- **Missing Locks**: Concurrent operations without proper locking
- **Timezone-naive**: `datetime.now()` without timezone awareness
- **Off-by-one**: Boundary condition checks using `>=` vs `>`
- **Early Return**: Timing attacks due to different response times

### Key Files to Examine

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios based on production incidents. Each scenario describes symptoms without revealing solutions:

| Scenario | Title | Severity | Hints At |
| `01-order-exposure-breach.md` | Customer Exceeds Risk Limits | P1 | Race conditions in risk checks |
| `02-market-close-orders.md` | Orders After Market Close | P2 | Timezone handling bugs |
| `03-penny-discrepancy.md` | Trade Value Discrepancies | P3 | Float vs Decimal precision |
| `04-token-refresh-storm.md` | Mobile Auth Failures | P2 | Token refresh races |
| `05-cache-stampede.md` | Market Data Overload | P1 | Cache stampede, hot keys |

Use these scenarios to:
1. Practice real-world debugging workflows
2. Understand how bugs manifest in production
3. Prioritize fixes based on business impact

## Success Criteria

- All 780+ tests pass
- Services start without errors
- No security vulnerabilities detected
- Performance tests complete within timeout

## Reward Function

The environment uses sparse rewards:

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
- Service isolation: +0.02 per fully passing service
- Chaos tests: +0.10 for passing chaos tests
- Regression penalty: -0.15 for re-breaking tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | OCO orders, Decimal precision, Snapshot caching, FIX gateway, TimescaleDB migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Market Surveillance Engine, Portfolio Analytics, Smart Order Router |

These tasks test different software engineering skills while using the same codebase.
