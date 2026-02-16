# DataNexus - Real-Time Data Pipeline & Analytics Platform Debug Challenge

## Objective

You are debugging a distributed real-time data pipeline and analytics platform built with Node.js microservices. The application has **120 intentional bugs** that cause tests to fail. Your goal is to identify and fix all bugs to achieve **100% test pass rate**.

**Difficulty Level**: Distinguished Engineer (24-48 hours expected)

## Getting Started

```bash
# Install dependencies
npm install

# Start services with Docker
docker compose up -d

# Run tests (will fail initially)
npm test

# Or with Docker
docker compose -f docker-compose.test.yml up --build
```

## Architecture

```
datanexus/
├── services/
│ ├── gateway/ # API Gateway (port 3000) - routing, rate limiting, WebSocket
│ ├── auth/ # Authentication (port 3001) - API keys, team management
│ ├── ingestion/ # Data Ingestion (port 3002) - schema validation, buffering
│ ├── transform/ # Data Transform (port 3003) - UDF execution, mapping
│ ├── router/ # Message Router (port 3004) - topic management, fan-out
│ ├── aggregate/ # Aggregation (port 3005) - windowing, rollups
│ ├── store/ # Time-Series Store (port 3006) - compaction, retention
│ ├── query/ # Query Engine (port 3007) - SQL-like interface
│ ├── alerts/ # Alert Engine (port 3008) - threshold & anomaly detection
│ ├── dashboards/ # Dashboards (port 3009) - CRUD, widgets, sharing
│ ├── connectors/ # Connector Framework (port 3010) - sources, sinks, webhooks
│ ├── scheduler/ # Job Scheduler (port 3011) - DAG execution, cron
│ ├── workers/ # Task Workers (port 3012) - distributed execution
│ ├── admin/ # Admin Service (port 3013) - tenant management
│ └── billing/ # Billing Service (port 3014) - usage metering, pricing
├── shared/ # Shared modules (clients, events, utils, stream)
├── tests/ # 750+ tests
│ ├── unit/
│ ├── integration/
│ ├── contract/
│ ├── chaos/
│ ├── security/
│ ├── performance/
│ └── system/
└── environment/ # RL environment wrapper
```

## Infrastructure

- **RabbitMQ 3.13** - Message broker for stream processing (port 5672)
- **PostgreSQL 16** x4 - pipeline_db (5432), users_db (5433), metrics_db (5434), billing_db (5435)
- **Redis 7** - Caching, stream state, pub/sub for live queries (port 6379)
- **Consul 1.17** - Service discovery, KV store (port 8500)
- **MinIO** - Data lake storage, connector artifacts (port 9000)
- **TimescaleDB** - Time-series storage via PostgreSQL extension

## Key Challenges

1. **15-Service Debugging**: Bugs span multiple services with complex interactions
2. **Stream Processing**: Windowing, watermarks, exactly-once semantics
3. **Distributed State**: Race conditions, split-brain, lock timeouts
4. **Cascading Failures**: Fixing one bug reveals others
5. **No Single Entry Point**: Setup bugs block different services independently
6. **Deep Dependency Chains**: Up to depth issues dependency chains

## Test Categories

| Category | Tests | Weight |
| Unit | ~410 | 1.0x |
| Integration | ~125 | 1.5x |
| Contract | ~30 | 2.0x |
| Chaos | ~70 | 3.0x |
| Security | ~70 | 2.5x |
| Performance | ~35 | 2.0x |
| System | ~55 | 3.0x |
| Stress | ~130 | 1.0x |

## Hints

### Setup Bugs (Fix These First!)

1. **L1**: Check `shared/index.js` - circular import chain
2. **L2**: Check RabbitMQ exchange declarations in event handlers
3. **L3**: Check `services/gateway/src/config.js` - missing await on async initialization
4. **L4**: Check `shared/events/index.js` - exchange must be declared before binding
5. **L8**: Check `shared/stream/index.js` - Redis stream group creation

### Common Bug Patterns

- **Off-by-one**: Window boundaries use `>` instead of `>=`
- **Float precision**: Aggregation and billing calculations
- **Missing await**: Async operations not awaited
- **Race conditions**: Concurrent updates without locking
- **Type coercion**: process.env values are strings
- **Prototype pollution**: Unsafe object merging in transform config

### Key Files to Examine

| `services/billing/src/services/metering.js` | Billing bugs |

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter:

| Scenario | Type | Symptoms |
| [Stream Processing Data Loss](./scenarios/01-stream-processing-data-loss.md) | PagerDuty Incident | Events missing from windows, memory growth |
| [Query Engine Security Audit](./scenarios/02-query-engine-security-audit.md) | Security Report | SQL injection, stale cache, boundary issues |
| [Alert Flapping Incident](./scenarios/03-alert-flapping-incident.md) | Customer Escalation | Duplicate alerts, missed escalations |
| [Aggregation Precision Errors](./scenarios/04-aggregation-precision-errors.md) | Slack Discussion | Wrong counts, histogram errors |
| [Scheduler Jobs Stuck](./scenarios/05-scheduler-jobs-stuck.md) | Grafana Alert | Out-of-order execution, split-brain |

These scenarios describe symptoms from an operator perspective - use them to practice realistic debugging workflows.

## Success Criteria

- All 750+ tests pass
- All 15 services start without errors
- No security vulnerabilities detected
- Stream processing maintains exactly-once semantics
- Distributed locks prevent split-brain
- Query engine handles SQL injection safely

## Reward Function

```
Pass Rate -> Reward (Very Sparse)
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
- Category completion: +0.03 per fully passing category
- Chaos test bonus: +0.10 for all chaos tests passing
- Bug fix bonus: up to +0.10 for fixing specific bugs
- Efficiency bonus: +0.05 for fast completion (only at 100%)
- Regression penalty: -0.15 for breaking previously passing tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Deduplication, window management, query batching, pipeline versioning, protobuf migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Data Quality Monitor, Schema Evolution Manager, Pipeline Orchestrator |

These tasks test different software engineering skills while using the same codebase.
