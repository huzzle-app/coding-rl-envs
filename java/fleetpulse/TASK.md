# FleetPulse - Real-Time Fleet Management Platform

## Task Description

You are debugging a real-time fleet management platform built with Java 21 and organized as 10 Spring Boot microservices. The platform handles vehicle tracking, route optimization, dispatch, billing, compliance, and analytics for commercial fleets with low-latency requirements.

The codebase contains issues across 10 microservices and a shared library that need to be identified and fixed. All 510+ tests must pass before the task is complete.

**Difficulty Level**: Principal/Staff Engineer (8-16 hours expected)

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Run all tests in Docker
docker compose -f docker-compose.test.yml up --build

# Or run tests locally with Maven
mvn test
```

## Architecture

FleetPulse is a multi-module Maven project with 10 Spring Boot microservices and a shared library:

```
fleetpulse/
├── shared/ # Shared library (config, events, security, concurrency utils)
├── gateway/ # API Gateway - Port 8000
├── auth/ # Authentication & Authorization - Port 8001
├── vehicles/ # Vehicle Registry & Telemetry - Port 8002
├── routes/ # Route Planning & Geofencing - Port 8003
├── dispatch/ # Dispatch & Assignment Engine - Port 8004
├── tracking/ # Real-Time GPS Tracking - Port 8005
├── billing/ # Invoicing & Payment Processing - Port 8006
├── analytics/ # Fleet Analytics & Reporting - Port 8007
├── notifications/ # Alerts & Notification Delivery - Port 8008
├── compliance/ # Regulatory Compliance (HOS, ELD) - Port 8009
├── environment/ # RL environment wrapper
├── pom.xml # Parent POM (multi-module build)
└── docker-compose.yml
```

### Services

| Service | Port | Purpose |
| Gateway | 8000 | REST API entry point, request routing, rate limiting |
| Auth | 8001 | JWT authentication, API keys, RBAC |
| Vehicles | 8002 | Vehicle CRUD, telemetry ingestion, maintenance state |
| Routes | 8003 | Route planning, geofence management, ETA calculation |
| Dispatch | 8004 | Job assignment, driver dispatch, optimization |
| Tracking | 8005 | Real-time GPS tracking, position history, speed monitoring |
| Billing | 8006 | Invoice generation, payment processing, revenue reporting |
| Analytics | 8007 | Fleet KPIs, fuel analytics, utilization reports |
| Notifications | 8008 | Push notifications, email, SMS, webhook delivery |
| Compliance | 8009 | Hours-of-service (HOS), ELD compliance, audit trail |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| Kafka 3.6 | Event streaming, inter-service messaging |
| PostgreSQL 15 | Persistent storage (vehicles_db, billing_db, compliance_db) |
| Redis 7 | Caching, rate limiting, distributed locks |
| Consul 1.17 | Service discovery, distributed configuration |

## Key Challenges

1. **Setup Hell**: Services will not start initially. You must fix circular dependencies (L1), Kafka topic auto-creation (L2), and Consul configuration loading (L3) before any tests can run.

2. **Multi-Service Debugging**: Bugs span multiple services. A fix in the shared library may unblock tests in several downstream services.

3. **Cascading Failures**: Some bugs depend on others being fixed first. Some bugs have explicit prerequisites, with dependency chains up to depth 5.

4. **Java-Specific Pitfalls**: Many bugs exploit Java-specific traps:
 - `BigDecimal.equals()` considers scale (1.0 != 1.00)
 - `@Transactional` does not work on self-invocation (proxy bypass)
 - Virtual threads get pinned on `synchronized` blocks
 - `Collectors.toMap()` throws on duplicate keys without merge function
 - `HashMap` with mutable keys loses entries after mutation

## Detailed Bug Listing

## Test Categories

| Category | Tests | Focus |
| Unit | ~200 | Individual methods, edge cases, data validation |
| Integration | ~120 | Service interactions, database queries, Kafka messaging |
| Concurrency | ~60 | Thread safety, race conditions, deadlock detection |
| Security | ~50 | Injection, authentication bypass, deserialization |
| Performance | ~40 | Throughput, latency, connection pool limits |
| Chaos | ~25 | Failure scenarios, network partitions, service restarts |
| System | ~15 | End-to-end fleet management workflows |

## Testing Approach

```bash
# Run all tests
mvn test

# Run tests for a specific module
mvn test -pl vehicles

# Run a specific test class
mvn test -pl billing -Dtest=InvoiceServiceTest

# Run with verbose output
mvn test -Dsurefire.useFile=true -q

# Run with parallel execution
mvn test -T 4
```

Test results are written to Surefire XML reports in each module's `target/surefire-reports/` directory.

## Success Criteria

- All 510+ tests pass across all 11 modules
- Services start without circular dependency errors
- No `ClassNotFoundException` or `NoSuchMethodError` at runtime
- No SQL injection, XXE, or deserialization vulnerabilities
- Financial calculations use `BigDecimal` with proper rounding
- No thread leaks, connection pool exhaustion, or deadlocks
- Virtual threads are not pinned by `synchronized` blocks

## Reward Function

The environment uses very sparse rewards (Principal difficulty):

```
Test Pass Rate -> Reward
< 25%   -> 0.00
25-39%  -> 0.05
40-54%  -> 0.12
55-69%  -> 0.22
70-84%  -> 0.38
85-94%  -> 0.55
95-99%  -> 0.78
100%    -> 1.00
```

Additional bonuses:
- Category completion: +0.01 per fully fixed category (12 categories)
- Service isolation: +0.01 per fully passing service (11 modules)
- Regression penalty: -0.03 per previously-passing test that now fails

## Java Patterns to Watch

The codebase uses many Java 21 features and Spring Boot patterns. Bugs exploit subtle
behavioral differences in these areas:

- `BigDecimal` equality semantics
- Spring AOP proxy invocation rules
- Virtual thread scheduling constraints
- `ThreadLocal` lifecycle in thread pools
- Stream collector edge cases with duplicate keys
- Record types with reference-type fields

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents, compliance audits, and operational alerts. These describe symptoms from an operator/user perspective without revealing the fixes.

| Scenario | Type | Description |
| [01-startup-failure-incident.md](./scenarios/01-startup-failure-incident.md) | PagerDuty | All services crashing on startup with circular dependencies and missing config |
| [02-financial-discrepancy-alert.md](./scenarios/02-financial-discrepancy-alert.md) | Finance | Customer invoices showing $47k in overcharges due to precision issues |
| [03-memory-cpu-saturation.md](./scenarios/03-memory-cpu-saturation.md) | PagerDuty | OOM kills, thread pool exhaustion, and ForkJoinPool starvation |
| [04-security-audit-findings.md](./scenarios/04-security-audit-findings.md) | Security | Pentest findings including SQL injection, JWT bypass, XXE, SSRF |
| [05-compliance-audit-failures.md](./scenarios/05-compliance-audit-failures.md) | Regulatory | DOT audit finding HOS calculation errors and timezone issues |

Use these scenarios to practice realistic debugging workflows, starting from symptoms and working toward root causes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Time-windowed route optimization, telemetry pipeline consolidation, GPS ingestion optimization, fuel card integration, TimescaleDB migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Driver Safety Scoring Service, Fuel Card Integration Service, Route Optimization Engine |

These tasks test different software engineering skills while using the same codebase.

## Hints

1. **Start with setup bugs** -- some configuration issues block services from starting. Fix these first to unblock downstream tests.
2. Some bug categories form dependency chains. Check which tests are blocked before investing time in later-stage fixes.
3. Concurrency bugs are the largest category. Focus on thread safety patterns.
4. Use `mvn test -pl <module>` to run targeted tests after each fix instead of the full suite.
5. The dependency graph means some bugs are not fixable until prerequisites are resolved. Plan your fix ordering accordingly.
