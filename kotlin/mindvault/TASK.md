# MindVault - Knowledge Management and AI-Assisted Research Platform

## Task Description

You are debugging a knowledge management platform built with Kotlin 1.9 and organized as 10 Ktor microservices with the Exposed ORM. The platform handles document management, semantic search, knowledge graphs, embeddings, real-time collaboration, billing, and analytics.

The codebase contains issues across 10 microservices and a shared library that need to be identified and fixed. All 510+ tests must pass before the task is complete.

**Difficulty Level**: Principal/Staff Engineer (8-16 hours expected)

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Run all tests in Docker
docker compose -f docker-compose.test.yml up --build

# Or run tests locally with Gradle
./gradlew test --no-daemon
```

## Architecture

MindVault is a multi-module Gradle project with 10 Ktor microservices and a shared library:

```
mindvault/
├── shared/ # Shared library (config, events, serialization, security utils)
├── gateway/ # API Gateway - Port 8080
├── auth/ # Authentication & Authorization - Port 8081
├── documents/ # Document Storage & Versioning - Port 8082
├── search/ # Full-Text Search & Query Parsing - Port 8083
├── graph/ # Knowledge Graph & Entity Relations - Port 8084
├── embeddings/ # Vector Embeddings & Similarity - Port 8085
├── collab/ # Real-Time Collaboration & WebSocket - Port 8086
├── billing/ # Subscription & Invoice Management - Port 8087
├── notifications/ # Alert & Notification Delivery - Port 8088
├── analytics/ # Usage Tracking & Metrics - Port 8089
├── environment/ # RL environment wrapper
├── build.gradle.kts # Root build file (multi-module)
├── settings.gradle.kts
└── docker-compose.yml
```

### Services

| Service | Port | Purpose |
| Gateway | 8080 | REST API entry point, request routing, rate limiting |
| Auth | 8081 | JWT authentication, API keys, RBAC |
| Documents | 8082 | Document CRUD, versioning, content storage |
| Search | 8083 | Full-text search, query parsing, ranking |
| Graph | 8084 | Knowledge graph, entity relationships, traversal |
| Embeddings | 8085 | Vector embeddings, similarity search, ML inference |
| Collab | 8086 | Real-time collaboration, WebSocket, CRDT |
| Billing | 8087 | Subscription management, invoicing, payments |
| Notifications | 8088 | Push notifications, email, webhook delivery |
| Analytics | 8089 | Usage tracking, reporting, metrics collection |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| Kafka 3.6 | Event streaming, inter-service messaging |
| PostgreSQL 16 | Persistent storage (per-service databases) |
| Redis 7 | Caching, session storage, rate limiting |
| Consul 1.17 | Service discovery, distributed configuration |

## Known Issues

Test failures indicate issues in core modules. Some infrastructure code may also need review.

## Key Challenges

1. **Setup Hell**: Modules will not compile initially. You must fix the Gradle root plugin configuration (L1) and HOCON substitution (L2) before any tests can run.

2. **Multi-Service Debugging**: Bugs span multiple services. A fix in the shared library may unblock tests in several downstream services.

3. **Cascading Failures**: Some bugs depend on others being fixed first. Some bugs have explicit prerequisites, with dependency chains up to depth 5+.

4. **Kotlin-Specific Pitfalls**: Many bugs exploit Kotlin-specific traps:
 - `runBlocking` in Ktor handler deadlocks the event loop
 - `GlobalScope.launch` leaks coroutines beyond parent lifecycle
 - `data class` with `ByteArray` uses reference equality
 - `copy()` performs shallow copy of mutable collections
 - Platform types (`String!`) from JDBC/Java are null-unsafe
 - `kotlinx.serialization.Transient` vs `kotlin.jvm.Transient`
 - `Exposed` requires `newSuspendedTransaction` in coroutine context

## Detailed Bug Listing

## Test Categories

| Category | Tests | Focus |
| Unit | ~200 | Individual methods, edge cases, data validation |
| Integration | ~120 | Service interactions, database queries, Kafka messaging |
| Coroutine | ~60 | Structured concurrency, cancellation, dispatcher safety |
| Security | ~50 | Injection, authentication bypass, deserialization |
| Performance | ~40 | Throughput, latency, connection pool limits |
| Chaos | ~25 | Failure scenarios, network partitions, service restarts |
| System | ~15 | End-to-end knowledge management workflows |

## Testing Approach

```bash
# Run all tests
./gradlew test --no-daemon

# Run tests for a specific module
./gradlew :documents:test --no-daemon

# Run a specific test class
./gradlew :billing:test --tests "com.mindvault.billing.BillingTests" --no-daemon

# Run with verbose output
./gradlew test --no-daemon --info

# Run with parallel execution
./gradlew test --no-daemon --parallel
```

Test results are written to JUnit XML reports in each module's `build/test-results/test/` directory.

## Success Criteria

- All 510+ tests pass across all 11 modules
- Services start without configuration errors
- No `SerializationException` or `ClassCastException` at runtime
- No SQL injection, XXE, or deserialization vulnerabilities
- Coroutines use structured concurrency (no GlobalScope leaks)
- Financial calculations use `BigDecimal` with proper rounding
- No thread leaks, connection pool exhaustion, or deadlocks
- Cache keys are stable and caches are bounded

## Reward Function

The environment uses very sparse rewards (Principal difficulty):

```
Bug Fix Rate -> Reward
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
- Category completion: +0.01 per fully fixed category (12 categories)
- Service isolation: +0.01 per fully passing service (11 modules)
- Regression penalty: -0.03 per previously-passing test that now fails

## Kotlin Patterns to Watch

```kotlin
// runBlocking in Ktor handler (BUG)
get("/api/data") {
 val result = runBlocking { fetchData() } // Deadlock!
 call.respond(result)
}
// Fix: remove runBlocking, handler is already suspend

// GlobalScope leak (BUG)
GlobalScope.launch { processInBackground() } // Leaks!
// Fix: use structured scope tied to lifecycle

// data class with ByteArray (BUG)
data class Doc(val content: ByteArray)
Doc(byteArrayOf(1)) == Doc(byteArrayOf(1)) // false!
// Fix: override equals/hashCode with contentEquals

// copy() shallow copy (BUG)
data class Meta(val tags: MutableList<String>)
val copy = original.copy()
copy.tags.add("new") // Also modifies original.tags!
// Fix: copy(tags = tags.toMutableList())

// Wrong @Transient (BUG)
@kotlin.jvm.Transient // Does NOT exclude from kotlinx.serialization!
val cached: String = ""
// Fix: use @kotlinx.serialization.Transient

// Exposed blocking transaction in coroutine (BUG)
suspend fun save(doc: Document) {
 transaction { /* blocks coroutine thread */ }
}
// Fix: newSuspendedTransaction(Dispatchers.IO) { }

// runCatching swallows cancellation (BUG)
runCatching { suspendingWork() } // Catches CancellationException!
// Fix: .onFailure { if (it is CancellationException) throw it }
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter:

| Scenario | Type | Description |
| [01-service-startup-failures.md](./scenarios/01-service-startup-failures.md) | PagerDuty Incident | Build failures, config errors, services won't start |
| [02-security-audit-findings.md](./scenarios/02-security-audit-findings.md) | Security Report | SQL injection, path traversal, JWT bypass, XXE |
| [03-coroutine-deadlocks.md](./scenarios/03-coroutine-deadlocks.md) | Customer Escalation | API timeouts, blocked coroutines, resource exhaustion |
| [04-data-corruption-sync.md](./scenarios/04-data-corruption-sync.md) | Slack Discussion | Document equality, cache issues, serialization errors |
| [05-billing-calculation-errors.md](./scenarios/05-billing-calculation-errors.md) | Finance Escalation | Incorrect invoices, transaction failures |

These scenarios describe **symptoms only** - use them to practice realistic debugging workflows.

## Hints

1. **Start with L category** -- setup bugs block module compilation. L1 (Gradle config) must be fixed first.
2. The serialization chain (F1-F7) is the longest at depth 6. Fix the `Instant` serializer registration first.
3. Coroutine bugs (A category) are the largest group with issues. Many downstream fixes depend on A1 (runBlocking).
4. Security bugs (I category) have diamond dependencies: I3 depends on both I1 and I2.
5. Use `./gradlew :module:test` to run targeted tests after each fix instead of the full suite.
6. Watch for `@Transactional` -> `newSuspendedTransaction` and `@Transient` -> `@kotlinx.serialization.Transient` confusion.
7. The dependency graph means some bugs are not fixable until prerequisites are resolved. Plan your fix ordering accordingly.
8. `data class` equality with `ByteArray`, `MutableList`, or value classes is a recurring theme across multiple bugs.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Hierarchical traversal, event sourcing, ANN indexing, semantic queries, Kafka migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Knowledge Gap Detector, Citation Analyzer, Auto-Tagging Service |

These tasks test different software engineering skills while using the same codebase.
