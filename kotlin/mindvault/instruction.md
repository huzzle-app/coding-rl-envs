# MindVault - Knowledge Management and AI-Assisted Research Platform

) | ## Task Overview

MindVault is a distributed knowledge management platform that handles document storage, semantic search, knowledge graph construction, AI-powered embeddings, real-time collaboration, billing, and analytics. The codebase across 10 microservices that you must identify and fix.

This is a Principal-level environment featuring complex distributed systems challenges including Kafka event streaming, coroutine concurrency, kotlinx.serialization pitfalls, Exposed ORM quirks, and modern Kotlin language features.

## Architecture

### Microservices

| Service | Port | Responsibility |
|---------|------|----------------|
| Gateway | 8080 | API Gateway, request routing, rate limiting |
| Auth | 8081 | JWT authentication, API keys, session management |
| Documents | 8082 | Document CRUD, versioning, content storage |
| Search | 8083 | Full-text search, query parsing, ranking |
| Graph | 8084 | Knowledge graph, entity relationships, traversal |
| Embeddings | 8085 | Vector embeddings, similarity search, ML inference |
| Collab | 8086 | Real-time collaboration, WebSocket, CRDT |
| Billing | 8087 | Subscription management, invoicing, payments |
| Notifications | 8088 | Email, push notifications, webhook delivery |
| Analytics | 8089 | Usage tracking, reporting, metrics collection |

### Infrastructure

- **Kafka 3.6**: Event streaming, inter-service messaging
- **PostgreSQL 16**: Primary data store (per-service databases)
- **Redis 7**: Caching, session storage, rate limiting
- **Consul 1.17**: Service discovery, distributed configuration

## Known Issues

The codebase needs debugging. Failures span configuration, service logic, and integration points.

## Getting Started

### Prerequisites

- Docker and Docker Compose
- JDK 21 (for local development, optional)
- Gradle 8.5+ (for local development, optional)

### Setup

```bash
cd /Users/amit/projects/terminal-bench-envs/kotlin/mindvault

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
./gradlew test --no-daemon

# Run tests for a specific module
./gradlew :documents:test --no-daemon

# Run a specific test class
./gradlew :billing:test --tests "com.mindvault.billing.BillingTests" --no-daemon

# Run with verbose output
./gradlew test --no-daemon --info
```

### Key Files

- **Entry Point**: `/Users/amit/projects/terminal-bench-envs/kotlin/mindvault/TASK.md` - Detailed bug descriptions and hints
- **Bug Mapping**: `/Users/amit/projects/terminal-bench-envs/kotlin/mindvault/environment/reward.py` - Bug dependency graph and reward calculation
- **Environment API**: `/Users/amit/projects/terminal-bench-envs/kotlin/mindvault/environment/setup.py` - Gymnasium-compatible interface
- **Service Code**: `<module>/src/main/kotlin/com/mindvault/<module>/`

## Success Criteria

Your goal is to fix all 80 bugs so that all 536 tests pass. The reward function uses 8 sparse thresholds:

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

1. **Start with Setup Bugs**: Fix Gradle plugin configuration and HOCON substitution issues first - these block module compilation
2. **Check Dependencies**: Some bugs have prerequisites - the bug dependency graph is in `environment/reward.py`
3. **Use Service Logs**: `docker compose logs <service-name>` shows startup errors and runtime issues
4. **Test Incrementally**: Run tests after each fix to verify progress and catch regressions
5. **Read TASK.md**: Contains detailed descriptions and hints for all issues
6. **Watch for Patterns**: Similar bugs often appear across multiple services

## Common Kotlin Pitfalls

- **`runBlocking` in Ktor handlers**: Causes deadlocks by blocking the event loop thread; use `suspend` functions instead
- **`GlobalScope.launch`**: Coroutines outlive their parent scope; use structured concurrency with `coroutineScope` or `supervisorScope`
- **Platform types from Java**: `String!` from JDBC/Java interop can be null at runtime despite no `?` in Kotlin; always add null checks
- **`data class` with `ByteArray`**: `equals()`/`hashCode()` use reference equality for arrays; override or use `contentEquals()`
- **`sealed when` exhaustiveness**: Adding a new subclass without updating `when` branches compiles but fails at runtime
- **`kotlinx.serialization` `@Transient`**: Must use `kotlinx.serialization.Transient`, not `kotlin.jvm.Transient`
- **`Exposed` `newSuspendedTransaction`**: Must use `newSuspendedTransaction` instead of `transaction` in coroutine context
- **`copy()` with mutable properties**: Shallow copy of mutable lists/maps shares references; mutating the copy mutates the original
- **Dispatchers.Unconfined**: Runs coroutine on the caller's thread initially, then on whatever thread resumes it; unsafe for thread-confined state

Good luck! This environment tests advanced Kotlin expertise including coroutine internals, Ktor pipeline mechanics, Exposed ORM patterns, kotlinx.serialization, and modern Kotlin language features.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Hierarchical traversal, event sourcing, ANN indexing, semantic queries, Kafka migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Knowledge Gap Detector, Citation Analyzer, Auto-Tagging Service |

These tasks test different software engineering skills while using the same codebase.
