# DataNexus - Real-Time Data Pipeline & Analytics Platform

## Task Overview

Fix bugs in a distributed real-time data pipeline and analytics platform built with Node.js microservices. DataNexus is a Distinguished Engineer-level environment (24-48 hours) that simulates a production-grade data pipeline with complex stream processing, distributed aggregation, and real-time analytics challenges.

## Architecture

DataNexus consists of 15 Node.js microservices communicating via RabbitMQ:

| Service | Port | Responsibility |
|---------|------|----------------|
| Gateway | 3000 | API Gateway, request routing, rate limiting, WebSocket for live queries |
| Auth | 3001 | Authentication, API keys, team management |
| Ingestion | 3002 | Data ingestion endpoints, schema validation, buffering |
| Transform | 3003 | Data transformation rules, UDF execution, mapping |
| Router | 3004 | Message routing, topic management, fan-out |
| Aggregate | 3005 | Real-time aggregation, windowing, rollups |
| Store | 3006 | Time-series storage, compaction, retention policies |
| Query | 3007 | Query engine, SQL-like interface, query optimization |
| Alerts | 3008 | Alert rules, threshold detection, anomaly detection |
| Dashboards | 3009 | Dashboard CRUD, widget rendering, sharing |
| Connectors | 3010 | Source/sink connectors, webhook receivers |
| Scheduler | 3011 | Job scheduling, DAG execution, cron |
| Workers | 3012 | Distributed task workers, backpressure |
| Admin | 3013 | Admin dashboard, tenant management |
| Billing | 3014 | Usage metering, data volume pricing |

## Infrastructure

- **RabbitMQ 3.13**: Message broker for stream processing
- **PostgreSQL 16**: Four databases (pipeline, users, metrics, billing)
- **Redis 7**: Caching, stream processing state, pub/sub for live queries
- **Consul 1.17**: Service discovery and configuration management
- **MinIO**: Data lake storage for connector artifacts
- **TimescaleDB**: Time-series storage via PostgreSQL extension

## Bug Categories

The issues span multiple categories typical of distributed Node.js data pipeline systems:

- **Setup/Configuration** (15): RabbitMQ connections, circular dependencies, startup races
- **Stream Processing** (12): Windowing, watermarks, late data, exactly-once delivery
- **Data Transformation** (10): Schema mapping, null handling, ReDoS, UDF execution
- **Query Engine** (8): SQL injection, plan cache, GROUP BY precision, pagination
- **Aggregation Pipeline** (10): Rolling sums, percentiles, HLL merge, rate calculation
- **Connector Framework** (8): Offset tracking, delivery guarantees, schema registry
- **Database/Transactions** (10): Connection pooling, sagas, outbox pattern, deadlocks
- **Alerting/Monitoring** (8): Float threshold, deduplication, escalation races
- **Caching** (8): Cache stampede, key collision, TTL race, write-through
- **Security** (10): SQL injection, XSS, SSRF, prototype pollution, IDOR
- **Scheduling** (8): DAG execution, cron timezone, leader election, job cleanup
- **Configuration** (8): Variable interpolation, env precedence, feature flags
- **Observability** (5): Trace context, correlation IDs, metric cardinality

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)

### Setup

```bash
cd js/datanexus

# Start infrastructure and services
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Run tests
npx jest --ci
```

### Initial State

The environment starts with **setup bugs** that prevent services from starting correctly. You must fix these foundational issues before the test suite can run successfully.

## Success Criteria

### Reward Function (8-Threshold, Very Sparse)

```
Pass Rate -> Reward
>= 100% -> 1.00
>= 95% -> 0.78
>= 85% -> 0.55
>= 70% -> 0.38
>= 55% -> 0.22
>= 40% -> 0.12
>= 25% -> 0.05
>= 10% -> 0.00
< 10% -> 0.00
```

**Target**: to achieve 100% test pass rate (tests) for maximum reward of 1.0.

### Test Execution

```bash
# Run full test suite
npx jest --ci

# Run specific category
npx jest tests/unit
npx jest tests/integration
npx jest tests/chaos
```

## Key Challenges

1. **15-Service Dependencies**: Bugs span multiple services with complex interactions
2. **Stream Processing Semantics**: Windowing, watermarks, exactly-once delivery
3. **Deep Dependency Chains**: Up to depth-issues dependency chains
4. **Diamond Dependencies**: Multiple bugs sharing common prerequisites
5. **Cross-Category Links**: Security bugs depend on transform/stream fixes
6. **Distributed Coordination**: Leader election, distributed locks, split-brain

## Tips

- Start with setup bugs (L-prefixed) to get services running
- Check RabbitMQ management UI at http://localhost:15672 (datanexus/datanexus)
- Monitor logs: `docker compose logs -f <service-name>`
- Use Consul UI at http://localhost:8500 for service discovery
- Test incrementally after each fix to avoid breaking working tests

## Architecture Patterns

- **API Gateway**: Single entry point with request routing and WebSocket
- **Event-Driven**: Async communication via RabbitMQ exchanges and queues
- **Stream Processing**: Windowed aggregation with watermark tracking
- **CQRS**: Separate read/write paths for time-series data
- **Circuit Breaker**: Fault tolerance for inter-service calls
- **Saga Pattern**: Distributed transactions with compensation logic
- **DAG Scheduling**: Directed acyclic graph for job dependencies

Good luck debugging!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Deduplication, window management, query batching, pipeline versioning, protobuf migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Data Quality Monitor, Schema Evolution Manager, Pipeline Orchestrator |

These tasks test different software engineering skills while using the same codebase.
