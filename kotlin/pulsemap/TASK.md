# PulseMap - Real-Time Geospatial Analytics Platform Debugging Challenge

## Overview

PulseMap is a real-time geospatial analytics platform built with Kotlin 1.9 and Ktor 2.3. It ingests sensor data streams, stores them in PostgreSQL with PostGIS extensions, caches map tiles in Redis, and serves vector/raster tiles to clients. The codebase contains issues across 7 categories that are blocking production deployment. Your task is to identify and fix these bugs to get all tests passing.

## Known Issues

The test suite has multiple failures across core modules. Issues appear to span business logic and infrastructure layers.

## Difficulty

**Senior Engineer Level** - Expected time: 2-4 hours

## Technology Stack

- **Language**: Kotlin 1.9.22
- **Framework**: Ktor 2.3.7, kotlinx.serialization, kotlinx.coroutines
- **ORM**: Exposed 0.44.1
- **Database**: PostgreSQL 15 + PostGIS 3.4
- **Cache**: Redis 7 (Lettuce client)
- **Build**: Gradle (Kotlin DSL)
- **Testing**: JUnit 5, Ktor Test Host, MockK, kotlinx-coroutines-test

## Getting Started

```bash
# Run all tests
./gradlew test

# Run specific test class
./gradlew test --tests "com.pulsemap.unit.SensorReadingTest"

# Run tests in a specific package
./gradlew test --tests "com.pulsemap.unit.*"

# Run with verbose output
./gradlew test --info

# Run with stacktrace
./gradlew test --stacktrace
```

**Important**: Setup bugs (L1-L4) prevent the application from starting correctly. The duplicate plugin install (L1) causes a crash on module load, missing serialization plugin (L2) prevents `@Serializable` from working at runtime, missing host config (L3) causes startup failure, and the database init inside a transaction (L4) deadlocks on connect. Fix these before tackling other categories.

Gradle build, Ktor configuration, and startup issues that block everything else.

**Tip**: Fix L1 and L2 first. L1 causes Ktor to crash with a `DuplicatePluginException` on module load. L2 causes all `@Serializable` data classes to fail at runtime because the compiler plugin that generates serializers is missing. L4 is a logical error where `transaction {}` requires an existing database connection, but the connection is being established inside the transaction.

### Category A: Coroutines/Async

Kotlin coroutine pitfalls: structured concurrency violations, blocking calls, and Flow misuse.

**Tip**: For A1, Ktor route handlers already run in a coroutine context; wrapping in `runBlocking` blocks the thread pool and can deadlock. Remove the `runBlocking` wrapper. For A2, use structured concurrency by accepting a `CoroutineScope` or using `supervisorScope`. For A3, `flowOn` must be placed in the flow chain before `collect`, not after. For A5, call `addressDeferred.await()` to actually get the computed result.

### Category B: Null Safety/Type Safety

Kotlin-specific null and type safety pitfalls that defeat the type system.

**Tip**: For B1, the private `parseWkt()` method returns `Pair<Double, Double>?` but the caller dereferences without null check. Add a `?.let` or `?:` elvis operator. For B2, between `containsKey` and `get`, another thread can evict the entry; use `get()` directly and check for null. For B3, when `name` is null, the `?.let` block is skipped entirely, meaning the column is not set at all in the INSERT statement. Use `it[SensorsTable.name] = name` directly (Exposed handles nullable columns). For B4, use `as? JsonArray ?: return@post ...` instead of the hard `as` cast.

### Category C: Data Class/Sealed Class

Kotlin data class and sealed class patterns that cause subtle runtime failures.

**Tip**: For C1, `DoubleArray` (and all Kotlin/JVM arrays) use reference equality in `equals()` and `hashCode()`. Replace with `List<Double>` for structural equality in data classes and HashSets. For C2, `data class.copy()` performs a shallow copy; mutable collections are shared between original and copy. Use `toMutableList()` to create a deep copy. For C3, add an explicit `is GeometryType.MultiPolygon` branch that sums the areas of its constituent polygons. For C4, register `QueryFilter.RadiusFilter::class` as a subclass in the `SerializersModule`.

### Category D: Ktor/Exposed Framework

Ktor pipeline and Exposed ORM framework-specific issues.

**Tip**: For D1, after `call.respond(HttpStatusCode.Unauthorized, ...)`, the interceptor must `return@intercept` to stop pipeline processing. Without it, the route handler executes with the unauthorized request. For D2, the coroutine launched in `GlobalScope` outlives the transaction; by the time it runs, the transaction is already committed and `TransactionManager.current()` is null. Move the notification outside the transaction block, or use `afterCommit {}`. For D3, set `shouldReturnGeneratedValues = false` in the `batchInsert` call to avoid generating `RETURNING *` for every row.

### Category E: Extension Functions/Generics

Kotlin-specific language features that create subtle bugs.

**Tip**: For E1, when a class defines a member extension function with the same signature as a file-level extension function, the member version takes priority within the class scope. The member version has `minLat` and `maxLat` swapped in the return statement. Either fix the swap or remove the member extension to let the correct file-level one be used. For E2, `processAndDeserialize<T>()` cannot call `deserialize<T>()` because `T` is not reified in the outer function. The type is erased at the JVM level. Either make `processAndDeserialize` an inline function with `reified T`, or pass a `KSerializer<T>` parameter explicitly.

### Category I: Security

Critical security vulnerabilities.

**Tip**: For I1, never interpolate user input into raw SQL strings. Use Exposed's type-safe DSL (`SensorsTable.select { SensorsTable.name eq name }`) or parameterized queries. For I2, validate that the resolved canonical path stays within the expected `tiles/` directory. Use `file.canonicalPath.startsWith(File("tiles").canonicalPath)` to reject traversal attempts.

## Test Structure

| Category | Package | Tests | Weight |
| Unit | `com.pulsemap.unit.*` | ~55 | 1.0x |
| Integration | `com.pulsemap.integration.*` | ~35 | 1.5x |
| Coroutines | `com.pulsemap.coroutines.*` | ~20 | 2.5x |
| Security | `com.pulsemap.security.*` | ~15 | 2.0x |
| **Total** | | **125+** | |

## Key Files to Investigate

## Scoring

Your score is based on the weighted percentage of tests passing:

| Pass Rate | Reward |
|-----------|--------|
| < 25% | 0.00 |
| 25-49% | 0.00-0.15 |
| 50-74% | 0.15-0.35 |
| 75-89% | 0.35-0.65 |
| 90-99% | 0.65-1.00 |
| 100% | 1.00 |

### Bonuses
- Category completion bonuses for fixing all bugs in a category
- Coroutine fix bonus (+3%) for resolving all async/coroutine issues
- Security fix bonus (+2%) for resolving all security vulnerabilities

### Penalties
- Regression penalty (-15%) for re-breaking previously passing tests

## Debugging Approach

### Phase 1: Fix Setup (L1-L4)

Get the application to start. Without this, almost no tests can run.

1. **L1** (Duplicate plugin): Ktor throws `DuplicatePluginException` when you call `install(ContentNegotiation)` twice. Remove the second install block or merge the configurations.
2. **L2** (Missing serialization plugin): Add `kotlin("plugin.serialization") version "1.9.22"` to the `plugins` block in `build.gradle.kts`. Without it, the `@Serializable` annotation has no effect and runtime serialization fails.
3. **L3** (Missing host config): Add `host = "0.0.0.0"` under the `ktor.deployment` section in `application.conf`, or ensure code that reads the host property has a fallback default.
4. **L4** (Database connect in transaction): Move `Database.connect()` outside the `transaction {}` block. The connection must be established before any transaction can begin.

### Phase 2: Fix Coroutine Issues (A1-A5)

Structured concurrency and dispatcher management are critical for correctness.

1. **A1** (runBlocking deadlock): Remove `runBlocking` - the Ktor handler is already a suspend function.
2. **A2** (GlobalScope): Replace with structured concurrency using a `CoroutineScope` parameter or `supervisorScope`.
3. **A3** (flowOn placement): Move `flowOn(Dispatchers.IO)` before `collect` in the flow chain.
4. **A4** (Unbounded channel): Use `Channel(Channel.BUFFERED)` or a fixed capacity like `Channel(64)`.
5. **A5** (Missing await): Call `addressDeferred.await()` instead of returning the hardcoded fallback.

### Phase 3: Fix Null/Type Safety (B1-B4)

Kotlin's null safety can be defeated in specific patterns.

1. **B1** (Platform type NPE): Add null check with `?:` or `?.let`.
2. **B2** (!! on map): Use `cache[key]` directly with null check instead of `containsKey` + `!!`.
3. **B3** (Nullable column skip): Use direct assignment `it[SensorsTable.name] = name` instead of `?.let`.
4. **B4** (Unsafe cast): Use `as?` safe cast with a fallback.

### Phase 4: Fix Data Class/Sealed Class (C1-C4)

Data class semantics and sealed class exhaustiveness.

### Phase 5: Fix Framework Issues (D1-D4)

Ktor pipeline and Exposed transaction semantics.

### Phase 6: Fix Extensions/Generics and Security (E1-E2, I1-I2)

Language features and security vulnerabilities.

## Architecture

```
pulsemap/
├── build.gradle.kts # L2
├── settings.gradle.kts
├── gradle.properties
├── src/
│ ├── main/
│ │ ├── kotlin/com/pulsemap/
│ │ │ ├── Application.kt # L1 - Ktor entry point
│ │ │ ├── config/
│ │ │ │ ├── DatabaseConfig.kt # L4
│ │ │ │ └── SerializationConfig.kt # C4
│ │ │ ├── model/
│ │ │ │ ├── SensorReading.kt # C1
│ │ │ │ ├── GeoPoint.kt # C2
│ │ │ │ ├── GeometryType.kt # C3
│ │ │ │ └── QueryFilter.kt # C4
│ │ │ ├── plugins/
│ │ │ │ └── AuthPlugin.kt # D1
│ │ │ ├── repository/
│ │ │ │ ├── SensorRepository.kt # B3, D3, I1
│ │ │ │ └── TileRepository.kt # D2
│ │ │ ├── routes/
│ │ │ │ ├── TileRoutes.kt # A1, I2
│ │ │ │ └── IngestionRoutes.kt # B4, D4
│ │ │ ├── service/
│ │ │ │ ├── IngestionService.kt # A2, A4
│ │ │ │ ├── SpatialAggregationService.kt # A3
│ │ │ │ ├── GeocodingService.kt # A5
│ │ │ │ ├── GeometryService.kt # B1, C3
│ │ │ │ ├── TileService.kt # B2
│ │ │ │ └── DeduplicationService.kt # C1
│ │ │ └── util/
│ │ │ ├── SpatialUtils.kt # E1
│ │ │ └── JsonUtils.kt # E2
│ │ └── resources/
│ │ └── application.conf # L3
│ └── test/
│ └── kotlin/com/pulsemap/
│ ├── unit/ # Unit tests
│ ├── integration/ # Integration tests
│ ├── coroutines/ # Coroutine tests
│ └── security/ # Security tests
├── environment/ # RL environment wrapper
├── Dockerfile
├── docker-compose.yml # PostgreSQL + PostGIS, Redis
└── docker-compose.test.yml # Test runner container
```

## Verification

After making fixes, verify with:

```bash
# Run all tests
./gradlew test

# Run specific test class
./gradlew test --tests "com.pulsemap.unit.SensorReadingTest"

# Run specific test method
./gradlew test --tests "com.pulsemap.unit.SensorReadingTest.test data class equals with DoubleArray"

# Run tests by category
./gradlew test --tests "com.pulsemap.unit.*"
./gradlew test --tests "com.pulsemap.integration.*"
./gradlew test --tests "com.pulsemap.coroutines.*"
./gradlew test --tests "com.pulsemap.security.*"

# Run with detailed output
./gradlew test --info 2>&1 | tail -50

# Check for compilation errors
./gradlew compileKotlin
```

## Kotlin-Specific Patterns to Watch

```kotlin
// Duplicate Ktor plugin install (BUG L1)
fun Application.module() {
 install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
 install(ContentNegotiation) { json(Json { ignoreUnknownKeys = false }) } // DuplicatePluginException!
}
// Fix: Remove the second install or merge into one

// Missing serialization plugin (BUG L2)
// build.gradle.kts
plugins {
 kotlin("jvm") version "1.9.22"
 // kotlin("plugin.serialization") version "1.9.22" // Must be present!
}
@Serializable // Has no effect without the plugin - serializer not generated
data class Foo(val x: Int)

// runBlocking inside coroutine (BUG A1)
get("/tiles/{z}/{x}/{y}") {
 val data = runBlocking { service.getTile(z, x, y) } // DEADLOCK!
 // Fix: Just call service.getTile(z, x, y) directly - handler is already a coroutine
}

// data class with Array field (BUG C1)
data class Reading(val values: DoubleArray) // equals/hashCode use reference equality!
val a = Reading(doubleArrayOf(1.0, 2.0))
val b = Reading(doubleArrayOf(1.0, 2.0))
a == b // FALSE! DoubleArray.equals uses identity
// Fix: Use List<Double> instead

// Shallow copy of MutableList in data class (BUG C2)
data class Point(val annotations: MutableList<String> = mutableListOf())
val original = Point()
val copy = original.copy()
copy.annotations.add("test")
original.annotations // ["test"] - shared reference!
// Fix: Override copy to deep-copy mutable fields, or use immutable List

// Platform type / nullable return ignored (BUG B1)
private fun parseWkt(wkt: String): Pair<Double, Double>? = null
fun use(wkt: String) {
 val result = parseWkt(wkt) // Nullable return
 result.first // NPE! No null check
}
// Fix: val result = parseWkt(wkt) ?: return defaultValue

// !! on Map.get after containsKey (BUG B2)
if (cache.containsKey(key)) {
 cache[key]!! // TOCTOU: can be null if evicted between checks
}
// Fix: val value = cache[key]; if (value != null) ...

// Member extension shadows file-level extension (BUG E1)
fun List<GeoPoint>.boundingBox(): BoundingBox { /* correct */ }

class SpatialUtils {
 fun List<GeoPoint>.boundingBox(): BoundingBox { /* buggy - shadows above */ }
 fun compute() = points.boundingBox() // Calls the buggy member version!
}

// Non-reified type calling reified function (BUG E2)
inline fun <reified T> decode(json: String): T = Json.decodeFromString(json)
fun <T> process(json: String): T = decode(json) // T is erased here!
// Fix: Make process() also inline with reified T

// Missing return@intercept after respond (BUG D1)
intercept(ApplicationCallPipeline.Plugins) {
 if (!authorized) {
 call.respond(HttpStatusCode.Unauthorized)
 // Missing return@intercept - pipeline continues!
 }
}

// SQL injection (BUG I1)
exec("SELECT * FROM sensors WHERE name = '$userInput'") // VULNERABLE!
// Fix: Use Exposed DSL: SensorsTable.select { SensorsTable.name eq userInput }
```

## Hints

1. **Start with L1 and L2**: Without the serialization plugin, all `@Serializable` classes fail at runtime. Without fixing the duplicate install, Ktor crashes on startup.
2. **runBlocking in coroutines**: Ktor handlers are already coroutines. Using `runBlocking` inside them blocks the thread pool and causes deadlocks.
3. **Array in data class**: `DoubleArray`, `IntArray`, etc. use reference equality in Kotlin data classes. Use `List<Double>` for structural equality.
4. **copy() is shallow**: `data class.copy()` does not deep-copy mutable collection fields. The original and copy share the same `MutableList` reference.
5. **sealed class when**: Always handle all branches explicitly. The `else` branch in a `when` on a sealed class hides missing cases.
6. **Exposed transactions**: `Database.connect()` must happen before any `transaction {}` block. Launching coroutines inside `transaction {}` lets them escape the transaction scope.
7. **Member extension priority**: A member extension function always shadows a file-level extension with the same signature within the class scope.
8. **Reified type erasure**: A non-reified type parameter `T` cannot be passed to a `reified` inline function because `T` is erased at the JVM level.
9. **Ktor pipeline flow**: After `call.respond()` in an interceptor, you must `return@intercept` to prevent the pipeline from continuing to the next handler.
10. **SQL injection in Kotlin**: String templates (`"... '$variable' ..."`) in raw SQL are just as dangerous as Java string concatenation.

Good luck! Remember: Kotlin's null safety and type system are powerful, but coroutines, data class semantics, and the Ktor/Exposed framework layers each have their own subtle pitfalls.

## Debugging Scenarios

For realistic debugging practice, check out the `scenarios/` directory which contains production-like incident reports, security audits, and Slack discussions that describe symptoms without revealing the fixes:

| Scenario | Type | Description |
| [01-startup-crash.md](./scenarios/01-startup-crash.md) | PagerDuty Incident | Application fails to start - plugin exceptions, serialization errors, config issues |
| [02-tile-service-deadlock.md](./scenarios/02-tile-service-deadlock.md) | Grafana Alert | Map tile API deadlocks under load - thread pool exhaustion |
| [03-sensor-deduplication-failures.md](./scenarios/03-sensor-deduplication-failures.md) | Customer Escalation | Duplicate sensor readings, data class equality issues |
| [04-security-audit-findings.md](./scenarios/04-security-audit-findings.md) | Security Report | SQL injection, path traversal, authorization bypass |
| [05-geocoding-async-issues.md](./scenarios/05-geocoding-async-issues.md) | Slack Discussion | Async/coroutine bugs, Flow misuse, memory growth |

These scenarios train debugging skills by presenting problems as operators and users would report them, without revealing the underlying code issues.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Tile layer compositing, visitor pattern refactoring, quadtree indexing, GeoJSON API, Redis cache migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Isochrone generator, spatial clustering, address autocomplete |

These tasks test different software engineering skills while using the same codebase.
