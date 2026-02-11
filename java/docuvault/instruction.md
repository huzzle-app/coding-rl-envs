# DocuVault - Enterprise Document Management System

 in a Java Spring Boot application for document management and collaboration.

## Overview

**Framework**: Spring Boot 3.2, Spring Data JPA
**Infrastructure**: PostgreSQL 16, Redis 7

## Bug Categories

| Category | IDs | Count | Description |
|----------|-----|-------|-------------|
| Setup/Config | L1-L4 | 4 | Circular bean dependency, @Profile mismatch, @Value parsing, Jackson version conflict |
| Concurrency | A1-A5 | 5 | ThreadLocal leak, DCL without volatile, CompletableFuture swallowed exception, ConcurrentModificationException, wrong monitor |
| Memory/Collections | B1-B4 | 4 | Mutable HashMap key, subList leak, Collectors.toMap duplicates, iterator invalidation |
| Spring Framework | C1-C4 | 4 | @Transactional self-invocation, @Async proxy bypass, prototype scope, @Cacheable key collision |
| Database/JPA | D1-D4 | 4 | N+1 query, LazyInitializationException, connection pool exhaustion, OptimisticLockException |
| Generics/Types | E1-E2 | 2 | Type erasure ClassCastException, wildcard capture failure |
| Security | I1-I4 | 4 | SQL injection, unsafe deserialization, path traversal, JWT "none" algorithm |

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/java/docuvault
docker compose up -d
mvn test
```

## Critical Setup Bugs

**L1 (Circular Bean Dependency)** blocks application startup. The Spring context cannot initialize due to circular dependencies between configuration beans. You must fix this first before any tests can run.

Other setup bugs (L2-L4) affect configuration loading, profile activation, and dependency versions.

## Common Java/Spring Pitfalls

- **@Transactional**: Self-invocation bypasses proxy, no transaction created
- **@Async**: Method must be public and called from outside class for proxy to work
- **ThreadLocal**: Must be cleaned up in web contexts to avoid memory leaks
- **Double-checked locking**: Requires `volatile` keyword to prevent instruction reordering
- **JPA LazyInitializationException**: Entity detached outside transaction scope
- **HashMap keys**: Must be immutable or properly implement equals/hashCode

## Success Criteria

- across 7 categories
- All tests passing
- No regressions introduced
- Spring application context starts successfully
- All security vulnerabilities patched

## Reward Function

Sparse reward with 5 thresholds:
- 25% tests passing → 0.0 reward
- 50% tests passing → 0.15 reward
- 75% tests passing → 0.35 reward
- 90% tests passing → 0.65 reward
- 100% tests passing → 1.0 reward

## Notes

- Maven test output shows: "Tests run: X, Failures: Y, Errors: Z, Skipped: W"
- Focus on setup bugs first (L1-L4) to get the application running
- Many bugs have dependencies - fixing one may unblock others
- Check Spring logs for circular dependency errors and proxy warnings
- Use `mvn test -B` for non-interactive batch mode

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Workflow Automation, Permission Consolidation, Search Optimization, Bulk Operations, Storage Migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Document Comparison Service, Retention Policy Engine, OCR Processing Pipeline |

These tasks test different software engineering skills while using the same codebase.
