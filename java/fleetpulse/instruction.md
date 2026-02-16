# FleetPulse - Real-Time Fleet Management Platform

## Task Overview

FleetPulse is a distributed fleet management platform built with Java 21 and organized as 10 Spring Boot microservices with a shared library. The platform handles real-time vehicle tracking, route optimization, dispatch coordination, billing, analytics, notifications, and compliance monitoring for commercial fleets.

The codebase contains approximately 66 bugs across 10 microservices and a shared library that you must identify and fix. All 510+ tests must pass before the task is complete.

This is a **Principal-level** environment featuring complex distributed systems challenges including Kafka event streaming, service mesh coordination, real-time data processing, financial calculations, and modern Java 21 patterns (virtual threads, sealed classes, records, pattern matching).

## Architecture

### Microservices

| Service | Port | Responsibility |
|---------|------|----------------|
| Gateway | 8000 | API Gateway, request routing, rate limiting |
| Auth | 8001 | Authentication, JWT tokens, session management |
| Vehicles | 8002 | Vehicle registry, maintenance schedules, telematics |
| Routes | 8003 | Route planning, optimization, ETA calculation |
| Dispatch | 8004 | Job assignment, driver matching, load balancing |
| Tracking | 8005 | Real-time GPS tracking, geofencing, alerts |
| Billing | 8006 | Invoicing, pricing, payment processing |
| Analytics | 8007 | Reporting, dashboards, KPI tracking |
| Notifications | 8008 | Email, SMS, push notifications, webhooks |
| Compliance | 8009 | DOT regulations, HOS tracking, auditing |

### Infrastructure

- **Kafka 3.6**: Event streaming, service communication, event sourcing
- **PostgreSQL 16**: Primary data store (per-service databases)
- **Redis 7**: Caching, session storage, rate limiting
- **Consul 1.17**: Service discovery, distributed configuration

## Bug Categories

| Category | Bugs | Description |
|----------|------|-------------|
| Setup/Config (L) | ~5 | Circular dependencies, Kafka config, Consul config, profile issues |
| Concurrency (A, C) | ~15 | Thread safety, race conditions, virtual thread pinning, deadlocks |
| Security (I) | ~8 | SQL injection, XXE, JWT bypass, timing attacks, SSRF, deserialization |
| Arithmetic/Precision (F, G) | ~12 | BigDecimal errors, integer division, overflow, floating-point |
| Event Sourcing (E) | ~4 | Ordering, isolation, batch performance |
| Data Structures (B, M) | ~6 | Mutable keys, EnumSet, collections, record equality |
| Observability (J) | ~4 | MDC propagation, trace context, metrics |
| Caching (C4, H) | ~3 | Key collisions, stampede prevention |
| Database/Resources (D, E3-E4) | ~3 | N+1 queries, connection pool, optimistic locking |
| Type Safety (K) | ~3 | Sealed classes, pattern matching, records |
| DateTime (G6, F5) | ~2 | Timezone errors |
| Distributed Systems (L1) | ~1 | Lock expiration |

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Run all tests in Docker
docker compose -f docker-compose.test.yml up --build

# Or run tests locally with Maven (requires Java 21)
mvn test -B -Dmaven.test.failure.ignore=true --fail-at-end

# Run tests for a specific module
mvn test -B -pl vehicles

# Run a specific test class
mvn test -B -pl billing -Dtest=BillingServiceTest
```

### Key Files

- **Entry Point**: `TASK.md` - Detailed bug descriptions and hints
- **Bug Mapping**: `environment/reward.py` - Bug dependency graph and reward calculation
- **Environment API**: `environment/setup.py` - Gymnasium-compatible interface

## Success Criteria

Your goal is to fix all bugs so that all 510+ tests pass. The reward function uses 8 sparse thresholds:

| Test Pass Rate | Reward |
|----------------|--------|
| < 25% | 0.00 |
| 25-39% | 0.05 |
| 40-54% | 0.12 |
| 55-69% | 0.22 |
| 70-84% | 0.38 |
| 85-94% | 0.55 |
| 95-99% | 0.78 |
| 100% | 1.00 |

**Note**: The reward function includes regression penalties (-0.03 per previously-passing test that now fails) and bonuses for completing entire categories or services (+0.01 each).

## Debugging Tips

1. **Start with Setup Bugs (L category)**: Fix circular bean dependencies and configuration issues first - these block service startup and prevent downstream tests from running
2. **Check Dependencies**: Some bugs have prerequisites - check `environment/reward.py` for the bug dependency graph
3. **Test Incrementally**: Run `mvn test -pl <module>` after each fix to verify progress and catch regressions
4. **Watch for Patterns**: Similar bugs often appear across multiple services
5. **The shared module is critical**: Many downstream service bugs depend on fixes in the shared library

## Common Java Pitfalls in This Codebase

- **@Transactional Self-Invocation**: Proxy bypass when calling methods on `this`
- **Virtual Thread Pinning**: `synchronized` blocks prevent virtual thread unmounting - use `ReentrantLock`
- **BigDecimal.equals()**: Considers scale (`1.0 != 1.00`), use `compareTo()` instead
- **Integer Division**: `compliantDays / totalDays` is 0 when both are int
- **ThreadLocal with Virtual Threads**: ThreadLocals leak when not cleaned up
- **Mutable Cache Keys**: Modifying objects used as HashMap keys breaks lookups
- **Collectors.toMap()**: Throws on duplicate keys without merge function
