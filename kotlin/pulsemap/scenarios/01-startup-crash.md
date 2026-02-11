# Incident Report: Application Startup Failure

## PagerDuty Alert

**Severity**: Critical (P0)
**Triggered**: 2024-02-18 02:15 UTC
**Acknowledged**: 2024-02-18 02:18 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: pulsemap-api-prod deployment failed
Cluster: pulsemap-prod-us-east-1
Namespace: geospatial
Pods: 0/3 Ready
```

## Timeline

**02:15 UTC** - Deployment triggered for release v2.4.1

**02:16 UTC** - All pods crash during startup with `CrashLoopBackOff`

```
NAME                           READY   STATUS             RESTARTS   AGE
pulsemap-api-6d4f8c9b7-j2k4l   0/1     CrashLoopBackOff   3          2m
pulsemap-api-6d4f8c9b7-m8n9p   0/1     CrashLoopBackOff   3          2m
pulsemap-api-6d4f8c9b7-q1r2s   0/1     CrashLoopBackOff   3          2m
```

**02:17 UTC** - Automatic rollback initiated but previous version (v2.4.0) also failing

**02:20 UTC** - Entire geospatial API offline

## Pod Logs Analysis

### Primary Crash (Pod j2k4l)

```
2024-02-18T02:16:03.142Z [main] INFO  Application - Starting PulseMap server...
2024-02-18T02:16:03.287Z [main] INFO  Application - Installing plugins...
2024-02-18T02:16:03.312Z [main] ERROR Application - Failed to start server
io.ktor.server.plugins.DuplicatePluginException: Plugin ContentNegotiation is already installed
    at io.ktor.server.application.ApplicationPluginKt.install(ApplicationPlugin.kt:98)
    at com.pulsemap.ApplicationKt.module(Application.kt:47)
    at io.ktor.server.engine.ApplicationEngineEnvironmentReloadingBase.instantiateAndConfigureApplication(ApplicationEngineEnvironmentReloadingBase.kt:275)
    at io.ktor.server.engine.ApplicationEngineEnvironmentReloadingBase.createApplication(ApplicationEngineEnvironmentReloadingBase.kt:141)
```

### Secondary Crash Pattern (Pod m8n9p)

When the duplicate plugin issue was temporarily patched, a different error emerged:

```
2024-02-18T02:22:45.891Z [main] INFO  Application - Starting PulseMap server...
2024-02-18T02:22:46.123Z [main] INFO  Application - Plugins installed successfully
2024-02-18T02:22:46.234Z [main] ERROR Application - Serialization failed
kotlinx.serialization.SerializationException: Serializer for class 'SensorReading' is not found.
Mark the class as @Serializable or provide the serializer explicitly.
    at kotlinx.serialization.internal.Platform_commonKt.serializerNotRegistered(Platform.kt:45)
    at kotlinx.serialization.SerializersKt__SerializersKt.serializer(Serializers.kt:194)
    at com.pulsemap.routes.IngestionRoutesKt.configureIngestionRoutes(IngestionRoutes.kt:34)
```

### Tertiary Crash Pattern (Pod q1r2s)

After both above issues appeared fixed, configuration error:

```
2024-02-18T02:28:12.456Z [main] INFO  Application - Starting PulseMap server...
2024-02-18T02:28:12.567Z [main] INFO  Application - Loading configuration...
2024-02-18T02:28:12.589Z [main] ERROR Application - Missing configuration property
io.ktor.server.config.ApplicationConfigurationException: Property ktor.deployment.host not found
    at io.ktor.server.config.HoconApplicationConfig.propertyOrNull(HoconApplicationConfig.kt:34)
    at com.pulsemap.ApplicationKt.module(Application.kt:23)
```

### Final Crash Pattern (After config fix attempt)

```
2024-02-18T02:35:08.789Z [main] INFO  Application - Connecting to database...
2024-02-18T02:35:09.012Z [main] INFO  Database - Initializing connection pool...
2024-02-18T02:35:39.012Z [main] ERROR Application - Database connection timeout
org.jetbrains.exposed.exceptions.ExposedSQLException: Connection attempt timed out
java.sql.SQLException: Cannot run SQL inside transaction block before database connection is established
    at org.jetbrains.exposed.sql.transactions.ThreadLocalTransactionManager.currentOrNull(ThreadLocalTransactionManager.kt:38)
    at com.pulsemap.config.DatabaseConfigKt.configureDatabaseConnection(DatabaseConfig.kt:28)
```

---

## Investigation Notes

### Engineering Discussion

**@dev.marco** (02:25 UTC):
> The duplicate plugin exception is clear - someone installed ContentNegotiation twice. But that's been in the codebase for weeks, why is it failing now?

**@dev.yuki** (02:28 UTC):
> Maybe a Ktor version update changed the behavior? Let me check the changelog... Yes, Ktor 2.3.7 enforces single plugin installation. Previous versions just logged a warning.

**@dev.marco** (02:32 UTC):
> OK, removed the duplicate. Now getting serialization errors. The `@Serializable` annotation is on all our data classes but it's acting like the compiler plugin isn't running.

**@dev.yuki** (02:35 UTC):
> Check `build.gradle.kts` - do we have `kotlin("plugin.serialization")` in the plugins block? The `kotlinx-serialization-json` dependency isn't enough - you need the compiler plugin too.

**@dev.marco** (02:40 UTC):
> Found it - the plugin line is commented out. Who did that?

**@dev.yuki** (02:45 UTC):
> Fixed serialization. Now hitting config issues. The code reads `ktor.deployment.host` but that property isn't in `application.conf`. Adding it now.

**@dev.marco** (02:50 UTC):
> OK, config fixed. But now database init is hanging and then timing out. The transaction is starting before the connection is established somehow.

---

## Build Configuration Excerpt

```kotlin
// build.gradle.kts
plugins {
    kotlin("jvm") version "1.9.22"
    id("io.ktor.plugin") version "2.3.7"
    // kotlin("plugin.serialization") version "1.9.22"  // TODO: enable after migration
}
```

## Application Configuration

```hocon
# application.conf
ktor {
    deployment {
        port = 8080
        # host = "0.0.0.0"  # Commented: using default
    }
}
```

---

## Customer Impact

- **Map tiles**: Completely unavailable
- **Sensor data ingestion**: All data being dropped
- **API status page**: Showing 100% failure rate
- **Estimated revenue impact**: $15,000/hour

---

## Affected Files

Based on stack traces:
- `build.gradle.kts` - Missing serialization plugin
- `src/main/kotlin/com/pulsemap/Application.kt` - Duplicate plugin installation
- `src/main/resources/application.conf` - Missing host configuration
- `src/main/kotlin/com/pulsemap/config/DatabaseConfig.kt` - Transaction/connection ordering

---

**Status**: INVESTIGATING
**Assigned**: @dev.marco, @dev.yuki
**Rollback Status**: Unable to rollback - previous versions have same issues
**ETA**: Unknown
