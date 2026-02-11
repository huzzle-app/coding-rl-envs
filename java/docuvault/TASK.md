# DocuVault - Enterprise Document Management Debugging Challenge

## Overview

DocuVault is an enterprise document management system built with Java 21 and Spring Boot 3.2. The codebase contains issues across 7 categories that are blocking production deployment. Your task is to identify and fix these bugs to get all tests passing.

## Difficulty

**Senior Engineer Level** - Expected time: 2-4 hours

## Technology Stack

- **Language**: Java 21
- **Framework**: Spring Boot 3.2, Spring Data JPA, Spring Security
- **ORM**: Hibernate 6 / JPA
- **Database**: PostgreSQL 16
- **Cache**: Redis 7 (Spring Cache)
- **Build**: Maven with Surefire
- **Testing**: JUnit 5, Spring Boot Test, Testcontainers

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Run all tests
mvn test

# Run specific test class
mvn test -Dtest=DocumentServiceTest

# Run tests in a specific package
mvn test -Dtest="com.docuvault.unit.*"

# Run with verbose output
mvn test -Dsurefire.useFile=true
```

**Important**: Setup bugs (L1-L4) prevent the application from starting correctly. The application context will fail to load until you fix the circular bean dependency. Fix these before tackling other categories.

## Bug Categories

### Category L: Setup/Configuration

Spring Boot configuration and startup issues that block everything else.

| Bug | Description | File |
|-----|-------------|------|
| L1 | Circular bean dependency between DocumentService and NotificationService | `src/main/java/com/docuvault/service/DocumentService.java`, `src/main/java/com/docuvault/service/NotificationService.java` |
| L2 | `@Profile("prod")` on MetadataExtractor bean prevents test profile from loading it | `src/main/java/com/docuvault/config/AppConfig.java` |
| L3 | Property `"10MB"` cannot be parsed as `long` via `@Value` | `src/main/resources/application.yml`, `src/main/java/com/docuvault/config/AppConfig.java` |
| L4 | Conflicting Jackson version in pom.xml (2.13 vs Spring Boot's 2.15+) | `pom.xml` |

**Tip**: Fix L1 first. The circular dependency prevents the entire ApplicationContext from loading, which blocks nearly all tests. Use `@Lazy` injection, extract an interface, or restructure the dependency.

### Category A: Concurrency

Java concurrency pitfalls: thread-safety, visibility, and synchronization.

| Bug | Description | File |
|-----|-------------|------|
| A1 | ThreadLocal leak in DocumentService - never removed after request | `src/main/java/com/docuvault/service/DocumentService.java` |
| A2 | Double-checked locking without `volatile` in VersionService singleton cache | `src/main/java/com/docuvault/service/VersionService.java` |
| A3 | CompletableFuture exception swallowed silently in ShareService | `src/main/java/com/docuvault/service/ShareService.java` |
| A4 | ConcurrentModificationException in NotificationService listener iteration | `src/main/java/com/docuvault/service/NotificationService.java` |
| A5 | `synchronized` on wrong monitor (prototype-scoped AuthService instance) | `src/main/java/com/docuvault/security/AuthService.java` |

**Tip**: For A2, the classic double-checked locking pattern in Java requires the field to be declared `volatile`. Without it, the JIT compiler can reorder writes, and another thread may see a partially constructed object. For A4, use `CopyOnWriteArrayList` or synchronize properly.

### Category B: Memory/Collections

Java collections pitfalls and memory management issues.

| Bug | Description | File |
|-----|-------------|------|
| B1 | Mutable HashMap key - Document's `hashCode()` uses mutable `name` field | `src/main/java/com/docuvault/model/Document.java`, `src/main/java/com/docuvault/service/VersionService.java` |
| B2 | `ArrayList.subList()` memory leak - subList retains reference to parent list | `src/main/java/com/docuvault/service/SearchService.java` |
| B3 | `Collectors.toMap()` throws on duplicate keys in DocumentController | `src/main/java/com/docuvault/controller/DocumentController.java` |
| B4 | Iterator invalidation in `FileUtils.cleanupTempFiles()` - modifying collection during iteration | `src/main/java/com/docuvault/util/FileUtils.java` |

**Tip**: For B1, either make `hashCode()`/`equals()` use only immutable fields (like `id`) or make the `name` field final. For B2, wrap the subList in `new ArrayList<>(...)` to break the reference to the parent. For B3, use the three-argument `toMap()` with a merge function.

### Category C: Spring Framework

Spring-specific bugs related to proxying, scoping, and caching.

| Bug | Description | File |
|-----|-------------|------|
| C1 | `@Transactional` self-invocation bypass - calling `this.method()` skips the proxy | `src/main/java/com/docuvault/service/DocumentService.java` |
| C2 | `@Async` self-invocation bypass - async method called from same class runs synchronously | `src/main/java/com/docuvault/service/DocumentService.java` |
| C3 | Prototype bean scope mismatch - prototype-scoped bean injected into singleton | `src/main/java/com/docuvault/service/NotificationService.java` |
| C4 | `@Cacheable` key collision for overloaded methods with same parameter types | `src/main/java/com/docuvault/service/DocumentService.java` |

**Tip**: C1 and C2 are the classic Spring proxy pitfall. When a bean calls its own `@Transactional` or `@Async` method via `this`, the call bypasses the proxy. Fix by injecting the bean into itself via `@Lazy`, using `ApplicationContext.getBean()`, or extracting the method to a separate service. For C3, use `@Scope(proxyMode = ScopedProxyMode.TARGET_CLASS)`.

### Category D: Database/JPA

Hibernate and JPA persistence issues.

| Bug | Description | File |
|-----|-------------|------|
| D1 | N+1 query problem - missing `JOIN FETCH` for `Document.versions` collection | `src/main/java/com/docuvault/repository/DocumentRepository.java` |
| D2 | `LazyInitializationException` accessing permissions outside open transaction | `src/main/java/com/docuvault/service/DocumentService.java` |
| D3 | Connection pool exhaustion - `EntityManager` not closed in manual query method | `src/main/java/com/docuvault/service/DocumentService.java` |
| D4 | `OptimisticLockException` not handled/retried in concurrent update scenario | `src/main/java/com/docuvault/util/FileUtils.java` |

**Tip**: For D1, add `@Query("SELECT d FROM Document d JOIN FETCH d.versions")` or use `@EntityGraph`. For D2, ensure the collection is accessed within a `@Transactional` scope. For D3, use try-with-resources or ensure `EntityManager.close()` in a `finally` block. For D4, add a retry loop with `@Retryable` or manual retry logic.

### Category E: Generics/Types

Java type system and generics pitfalls.

| Bug | Description | File |
|-----|-------------|------|
| E1 | Type erasure `ClassCastException` - raw `List` mixed with generic `List<Document>` | `src/main/java/com/docuvault/service/SearchService.java` |
| E2 | Wildcard capture failure - attempting to add to `List<? extends Permission>` | `src/main/java/com/docuvault/service/ShareService.java` |

**Tip**: For E1, ensure all List references are properly parameterized and avoid raw types. At runtime, generics are erased, so casting an `Object` from a raw List to `Document` will throw `ClassCastException` if the actual type is different. For E2, `List<? extends Permission>` is read-only for additions; change to `List<Permission>` or use a helper method with a captured type parameter.

### Category I: Security

Critical security vulnerabilities.

| Bug | Description | File |
|-----|-------------|------|
| I1 | SQL injection via string concatenation in custom query in SecurityConfig | `src/main/java/com/docuvault/config/SecurityConfig.java` |
| I2 | `ObjectInputStream` deserialization of untrusted data in DocumentController | `src/main/java/com/docuvault/controller/DocumentController.java` |
| I3 | Path traversal in AdminController file download endpoint | `src/main/java/com/docuvault/controller/AdminController.java` |
| I4 | JWT "none" algorithm accepted in JwtTokenProvider | `src/main/java/com/docuvault/security/JwtTokenProvider.java` |

**Tip**: For I1, never concatenate user input into SQL strings; use parameterized queries or Spring Data JPA's `@Query` with named parameters. For I2, never deserialize untrusted input with `ObjectInputStream`; use JSON/Jackson instead or implement an `ObjectInputFilter`. For I3, validate and canonicalize the file path, rejecting `..` sequences. For I4, explicitly reject the "none" algorithm when validating JWT tokens.

## Test Structure

| Category | Package | Tests | Weight |
|----------|---------|-------|--------|
| Unit | `com.docuvault.unit.*` | ~55 | 1.0x |
| Integration | `com.docuvault.integration.*` | ~35 | 1.5x |
| Concurrency | `com.docuvault.concurrency.*` | ~20 | 2.5x |
| Security | `com.docuvault.security.*` | ~15 | 2.0x |
| **Total** | | **125+** | |

## Key Files to Investigate

| File | Bug Categories |
|------|---------------|
| `src/main/java/com/docuvault/service/DocumentService.java` | L1, A1, C1, C2, C4, D2, D3 |
| `src/main/java/com/docuvault/service/NotificationService.java` | L1, A4, C3 |
| `src/main/java/com/docuvault/service/VersionService.java` | A2, B1 |
| `src/main/java/com/docuvault/service/SearchService.java` | B2, E1 |
| `src/main/java/com/docuvault/service/ShareService.java` | A3, E2 |
| `src/main/java/com/docuvault/controller/DocumentController.java` | B3, I2 |
| `src/main/java/com/docuvault/controller/AdminController.java` | I3 |
| `src/main/java/com/docuvault/config/AppConfig.java` | L2, L3 |
| `src/main/java/com/docuvault/config/SecurityConfig.java` | I1 |
| `src/main/java/com/docuvault/security/JwtTokenProvider.java` | I4 |
| `src/main/java/com/docuvault/security/AuthService.java` | A5 |
| `src/main/java/com/docuvault/model/Document.java` | B1 |
| `src/main/java/com/docuvault/repository/DocumentRepository.java` | D1 |
| `src/main/java/com/docuvault/util/FileUtils.java` | B4, D4 |
| `src/main/java/com/docuvault/util/MetadataExtractor.java` | L2 |
| `pom.xml` | L4 |
| `src/main/resources/application.yml` | L3 |

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
- Concurrency fix bonus (+3%) for resolving all thread-safety issues
- Security fix bonus (+2%) for resolving all security vulnerabilities

### Penalties
- Regression penalty (-15%) for re-breaking previously passing tests

## Debugging Approach

### Phase 1: Fix Setup (L1-L4)

Get the application context to load. Without this, almost no tests can run.

1. **L1** (Circular dependency): Look at `DocumentService` and `NotificationService`. They inject each other, causing Spring to fail on startup. Break the cycle with `@Lazy` on one injection point.
2. **L2** (Profile mismatch): `MetadataExtractor` is annotated with `@Profile("prod")`. Tests run under the `test` profile, so the bean is never created. Remove the profile restriction or add `test` to the profile list.
3. **L3** (Property parsing): `@Value("${docuvault.max-file-size}")` tries to inject `"10MB"` as a `long`. Use Spring's `DataSize` type or parse the string manually.
4. **L4** (Jackson conflict): `pom.xml` declares an explicit Jackson dependency at version 2.13, conflicting with Spring Boot 3.2's managed version (2.15+). Remove the explicit version or use `${jackson.version}` from the parent BOM.

### Phase 2: Fix Spring Framework Issues (C1-C4)

Many other bugs depend on proper Spring proxy behavior.

1. **C1** (@Transactional self-invocation): The fix unblocks D1, D2, and C2.
2. **C2** (@Async self-invocation): Similar proxy issue in the same class.
3. **C3** (Prototype scope): Singleton holds a reference to a single prototype instance. Use `@Scope(proxyMode = ScopedProxyMode.TARGET_CLASS)` or `ObjectProvider<T>`.
4. **C4** (Cache key collision): Two overloaded methods share a `@Cacheable` key. Use explicit `key` attribute with SpEL.

### Phase 3: Fix Database/JPA (D1-D4)

These often surface as integration test failures.

### Phase 4: Fix Concurrency (A1-A5)

Run tests with thread dumps enabled if needed. Focus on thread-safety patterns.

### Phase 5: Fix Collections and Types (B1-B4, E1-E2)

These are subtle runtime errors that may only appear under specific data conditions.

### Phase 6: Fix Security (I1-I4)

Review every place user input touches SQL, file paths, or deserialization.

## Architecture

```
docuvault/
├── src/
│ ├── main/
│ │ ├── java/com/docuvault/
│ │ │ ├── DocuVaultApplication.java # Spring Boot entry point
│ │ │ ├── config/ # Configuration classes
│ │ │ │ ├── AppConfig.java # L2, L3
│ │ │ │ ├── CacheConfig.java # Redis/Spring Cache setup
│ │ │ │ └── SecurityConfig.java # I1
│ │ │ ├── controller/ # REST endpoints
│ │ │ │ ├── DocumentController.java # B3, I2
│ │ │ │ └── AdminController.java # I3
│ │ │ ├── model/ # JPA entities
│ │ │ │ ├── Document.java # B1
│ │ │ │ ├── User.java
│ │ │ │ └── Permission.java
│ │ │ ├── repository/ # Spring Data JPA repos
│ │ │ │ └── DocumentRepository.java # D1
│ │ │ ├── service/ # Business logic
│ │ │ │ ├── DocumentService.java # L1, A1, C1, C2, C4, D2, D3
│ │ │ │ ├── VersionService.java # A2, B1
│ │ │ │ ├── SearchService.java # B2, E1
│ │ │ │ ├── ShareService.java # A3, E2
│ │ │ │ └── NotificationService.java # L1, A4, C3
│ │ │ ├── security/ # Auth and JWT
│ │ │ │ ├── JwtTokenProvider.java # I4
│ │ │ │ └── AuthService.java # A5
│ │ │ └── util/ # Utilities
│ │ │ ├── FileUtils.java # B4, D4
│ │ │ └── MetadataExtractor.java # L2
│ │ └── resources/
│ │ └── application.yml # L3
│ └── test/
│ └── java/com/docuvault/
│ ├── unit/ # Unit tests
│ ├── integration/ # Integration tests
│ ├── concurrency/ # Thread-safety tests
│ └── security/ # Security tests
├── pom.xml # L4
├── environment/ # RL environment wrapper
├── Dockerfile
├── docker-compose.yml # PostgreSQL 16, Redis 7
└── docker-compose.test.yml # Test runner container
```

## Verification

After making fixes, verify with:

```bash
# Run all tests
mvn test

# Run specific test class
mvn test -Dtest=DocumentServiceTest

# Run specific test method
mvn test -Dtest="DocumentServiceTest#test_self_invocation_transactional"

# Run tests by category
mvn test -Dtest="com.docuvault.unit.*"
mvn test -Dtest="com.docuvault.integration.*"
mvn test -Dtest="com.docuvault.concurrency.*"
mvn test -Dtest="com.docuvault.security.*"

# Run with Surefire report generation
mvn test -Dsurefire.useFile=true
ls target/surefire-reports/TEST-*.xml

# Check for compilation errors
mvn compile
```

## Java-Specific Patterns to Watch

```java
// Circular dependency (BUG L1)
@Service
class ServiceA {
 @Autowired ServiceB b; // ServiceB also @Autowired ServiceA -> circular!
}
// Fix: @Lazy on one injection, or extract shared logic

// @Transactional self-invocation (BUG C1)
@Service
class MyService {
 @Transactional
 public void innerMethod() { /* ... */ }

 public void outerMethod() {
 this.innerMethod();
 }
}

// Double-checked locking without volatile (BUG A2)
class Singleton {
 private static Singleton instance;
 public static Singleton get() {
 if (instance == null) {
 synchronized (Singleton.class) {
 if (instance == null) {
 instance = new Singleton(); // Without volatile, may be reordered
 }
 }
 }
 return instance;
 }
}

// Mutable HashMap key (BUG B1)
Map<Document, List<Version>> map = new HashMap<>();
map.put(doc, versions);
doc.setName("new name"); // hashCode changes!
map.get(doc); // Returns null - key is lost

// SQL injection (BUG I1)
String query = "SELECT * FROM users WHERE name = '" + userInput + "'";
// Fix: Use parameterized queries or JPA named parameters
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter. Each scenario describes **symptoms only** - use them to practice real-world debugging:

| Scenario | Type | Primary Symptoms |
|----------|------|------------------|
| [01-application-startup-failure.md](./scenarios/01-application-startup-failure.md) | PagerDuty Incident | Bean creation errors, circular dependencies, profile mismatches |
| [02-security-penetration-test.md](./scenarios/02-security-penetration-test.md) | Security Report | SQL injection, path traversal, insecure deserialization, JWT bypass |
| [03-concurrent-document-corruption.md](./scenarios/03-concurrent-document-corruption.md) | Customer Escalation | Race conditions, memory leaks, silent async failures |
| [04-database-performance-degradation.md](./scenarios/04-database-performance-degradation.md) | Grafana Alert | N+1 queries, connection exhaustion, LazyInitializationException |
| [05-cache-inconsistency-slack.md](./scenarios/05-cache-inconsistency-slack.md) | Slack Thread | Cache key collisions, type erasure, collection pitfalls |

See [scenarios/README.md](./scenarios/README.md) for full index and investigation tips.

## Hints

1. **Start with L1**: Fix the circular bean dependency first - the ApplicationContext cannot load without it, so nearly all tests will fail
2. **Profile matters**: Check `@Profile` annotations - test beans need to be available under the test profile
3. **Spring proxy pitfall**: `this.method()` calls bypass `@Transactional`, `@Async`, and `@Cacheable` proxies
4. **Check pom.xml**: Explicit dependency versions can conflict with Spring Boot's managed dependencies
5. **volatile for DCL**: Java's double-checked locking idiom requires `volatile` on the shared field
6. **subList retains parent**: `List.subList()` returns a view backed by the original list; wrap in `new ArrayList<>()` to detach
7. **Collectors.toMap()**: The default `toMap()` throws `IllegalStateException` on duplicate keys
8. **EntityManager lifecycle**: Always close EntityManager in a `finally` block or use try-with-resources
9. **JWT "none" attack**: Always validate the algorithm in the JWT header; reject "none" explicitly

Good luck! Remember: Spring's magic is powerful, but understanding the proxy model is essential for debugging.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Workflow Automation, Permission Consolidation, Search Optimization, Bulk Operations, Storage Migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Document Comparison Service, Retention Policy Engine, OCR Processing Pipeline |

These tasks test different software engineering skills while using the same codebase.
