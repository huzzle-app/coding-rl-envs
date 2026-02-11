# FleetPulse - Real-Time Fleet Management Platform

) | ## Task Overview

FleetPulse is a distributed fleet management platform that handles real-time vehicle tracking, route optimization, dispatch coordination, and compliance monitoring. The codebase across 10 microservices that you must identify and fix.

This is a Principal-level environment featuring complex distributed systems challenges including Kafka event streaming, service mesh coordination, real-time data processing, financial calculations, and modern Java patterns.

## Architecture

### Microservices

| Service | Port | Responsibility |
|---------|------|----------------|
| Gateway | 8080 | API Gateway, request routing, rate limiting |
| Auth | 8081 | Authentication, JWT tokens, session management |
| Vehicles | 8082 | Vehicle registry, maintenance schedules, telematics |
| Routes | 8083 | Route planning, optimization, ETA calculation |
| Dispatch | 8084 | Job assignment, driver matching, load balancing |
| Tracking | 8085 | Real-time GPS tracking, geofencing, alerts |
| Billing | 8086 | Invoicing, pricing, payment processing |
| Analytics | 8087 | Reporting, dashboards, KPI tracking |
| Notifications | 8088 | Email, SMS, push notifications, webhooks |
| Compliance | 8089 | DOT regulations, HOS tracking, auditing |

### Infrastructure

- **Kafka 3.6**: Event streaming, service communication, event sourcing
- **PostgreSQL 15**: Primary data store (per-service databases)
- **Redis 7**: Caching, session storage, rate limiting
- **Consul 1.17**: Service discovery, distributed configuration

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Java 21 (for local development, optional)
- Maven 3.9+ (for local development, optional)

### Setup

```bash
cd /Users/amit/projects/terminal-bench-envs/java/fleetpulse

# Start infrastructure and services
docker compose up -d

# Wait for services to be healthy (30-60 seconds)
docker compose ps

# Run tests
docker compose -f docker-compose.test.yml up --build
```

### Running Tests Locally

```bash
# Run all tests
mvn test -B

# Run specific service tests
mvn test -B -pl gateway

# Run with verbose output
mvn test -B -X
```

### Key Files

- **Entry Point**: `/Users/amit/projects/terminal-bench-envs/java/fleetpulse/TASK.md` - Detailed bug descriptions and hints
- **Bug Mapping**: `/Users/amit/projects/terminal-bench-envs/java/fleetpulse/environment/reward.py` - Bug dependency graph and reward calculation
- **Environment API**: `/Users/amit/projects/terminal-bench-envs/java/fleetpulse/environment/setup.py` - Gymnasium-compatible interface
- **Service Code**: `/Users/amit/projects/terminal-bench-envs/java/fleetpulse/services/*/src/main/java/com/fleetpulse/*/`

## Success Criteria

Your goal is to fix bugs . The reward function uses 8 sparse thresholds:

| Test Pass Rate | Reward |
|----------------|--------|
| < 10% | 0.00 |
| 10-24% | 0.00 |
| 25-39% | 0.05 |
| 40-54% | 0.12 |
| 55-69% | 0.22 |
| 70-84% | 0.38 |
| 85-94% | 0.55 |
| 95-99% | 0.78 |
| 100% | 1.00 |

**Note**: The reward function includes regression penalties - re-breaking previously passing tests will decrease your reward.

## Debugging Tips

1. **Start with Setup Bugs**: Fix circular bean dependencies and configuration issues first - these block service startup
2. **Check Dependencies**: Some bugs have prerequisites - the bug dependency graph is in `environment/reward.py`
3. **Use Service Logs**: `docker compose logs <service-name>` shows startup errors and runtime issues
4. **Test Incrementally**: Run tests after each fix to verify progress and catch regressions
5. **Read TASK.md**: Contains detailed descriptions and hints for all issues
6. **Watch for Patterns**: Similar bugs often appear across multiple services

## Common Pitfalls

- **@Transactional Self-Invocation**: Proxy bypass when calling methods on `this` - use Spring's AopContext or extract to another bean
- **Virtual Thread Pinning**: Synchronized blocks and certain blocking operations prevent virtual thread unmounting
- **Kafka Consumer Rebalancing**: Improper offset management causes duplicate/lost messages
- **BigDecimal Equality**: Use `compareTo()` not `equals()` for numerical comparison
- **ThreadLocal with Virtual Threads**: ThreadLocals leak when virtual threads are pooled
- **Mutable Cache Keys**: Modifying objects used as HashMap keys breaks lookups
- **LazyInitializationException**: Accessing lazy-loaded JPA entities outside transaction scope

Good luck! This environment tests advanced Java expertise including Spring Framework internals, JVM concurrency, distributed systems, and modern Java language features.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Time-windowed route optimization, telemetry pipeline consolidation, GPS ingestion optimization, fuel card integration, TimescaleDB migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Driver Safety Scoring Service, Fuel Card Integration Service, Route Optimization Engine |

These tasks test different software engineering skills while using the same codebase.
