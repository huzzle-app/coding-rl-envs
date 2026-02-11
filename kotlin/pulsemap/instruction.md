# PulseMap - Real-Time Geospatial Analytics Platform

 in a Kotlin Ktor application for geospatial sensor data ingestion, spatial aggregation, and tile-based map rendering.

## Overview

**Framework**: Ktor 2.3, Exposed ORM
**Infrastructure**: PostgreSQL 16 + PostGIS, Redis 7

## Known Issues

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/kotlin/pulsemap
docker compose up -d
./gradlew test --no-daemon
```

## Critical Setup Bugs

**L1 (Content Negotiation)** blocks application startup. The Ktor server installs `ContentNegotiation` twice, causing a `DuplicatePluginException`. You must fix this first before any tests can run.

Other setup bugs (L2-L4) affect serialization configuration, HOCON property resolution, and Exposed database initialization order.

## Common Kotlin/Ktor Pitfalls

- **runBlocking in coroutine context**: Using `runBlocking` inside a Ktor handler (already a coroutine) causes thread starvation and deadlocks
- **GlobalScope**: Coroutines launched in `GlobalScope` are not cancelled on shutdown, leading to resource leaks
- **Platform types**: Java interop returns platform types (`T!`) that bypass null checks at compile time but crash at runtime
- **Data class with arrays**: `data class` `equals()`/`hashCode()` use referential equality for arrays, not structural
- **Sealed class when**: Non-exhaustive `when` on sealed class compiles with `else` but silently drops new subtypes
- **Exposed transactions**: Calling `suspend` functions inside `transaction {}` blocks can cause coroutine context issues
- **Extension vs member**: Member functions always win over extension functions with the same signature
- **Reified type parameters**: Generic type info is erased at runtime unless the function is `inline` with `reified`

## Success Criteria

- across 7 categories
- All tests passing
- No regressions introduced
- Ktor application starts successfully
- All security vulnerabilities patched

## Reward Function

Sparse reward with 5 thresholds:
- 25% tests passing -> 0.0 reward
- 50% tests passing -> 0.15 reward
- 75% tests passing -> 0.35 reward
- 90% tests passing -> 0.65 reward
- 100% tests passing -> 1.0 reward

Additional bonuses for fixing all coroutine bugs (+0.03) and all security bugs (+0.02). Regression penalty of -0.02 per test that was previously passing but now fails.

## Notes

- Gradle test output: JUnit XML reports in `build/test-results/test/`
- Focus on setup bugs first (L1-L4) to get the application running
- Many bugs have dependencies - fixing one may unblock others
- Check Ktor logs for plugin installation errors and serialization failures
- Use `./gradlew test --no-daemon` for consistent test runs

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Tile layer compositing, visitor pattern refactoring, quadtree indexing, GeoJSON API, Redis cache migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Isochrone generator, spatial clustering, address autocomplete |

These tasks test different software engineering skills while using the same codebase.
