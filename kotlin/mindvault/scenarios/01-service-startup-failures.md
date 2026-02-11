# Incident Report: MindVault Services Failing to Start

## PagerDuty Alert

**Severity**: Critical (P0)
**Triggered**: 2024-02-20 02:15 UTC
**Acknowledged**: 2024-02-20 02:18 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: mindvault-deploy-prod FAILED
Pipeline: deploy-prod-us-east-1
Stage: gradle-build
Exit Code: 1
Duration: 4m 23s
```

## Timeline

**02:15 UTC** - Deployment pipeline failed at Gradle build stage

**02:18 UTC** - On-call engineer acknowledged, began investigation

**02:25 UTC** - Attempted manual build in fresh environment, same failure

**02:32 UTC** - Identified multiple distinct failure modes depending on which module loads first

**02:45 UTC** - Escalated to platform team; services remain down in staging

## Build Output

### Primary Failure - Gradle Configuration

```
FAILURE: Build failed with an exception.

* Where:
Build file '/app/build.gradle.kts' line: 12

* What went wrong:
A problem occurred evaluating root project 'mindvault'.
> Plugin [id: 'org.jetbrains.kotlin.jvm'] was not found in any of the following sources:
  - Gradle Core Plugins (not a core Gradle plugin)

* Try:
> Run with --stacktrace option to get the stack trace.
> Run with --info or --debug option to get more log output.

BUILD FAILED in 8s
```

### Secondary Failure - Module Resolution

After attempting workarounds for the first issue:

```
FAILURE: Build failed with an exception.

* What went wrong:
Project 'notifications' not found in root project 'mindvault'.

* Try:
> Run with --stacktrace option to get the stack trace.

BUILD FAILED in 3s
```

### Runtime Configuration Error

When build eventually succeeds but services start:

```
Exception in thread "main" com.typesafe.config.ConfigException$UnresolvedSubstitution:
reference.conf @ jar:file:/app/shared/build/libs/shared.jar!/reference.conf: 12:
Could not resolve substitution to a value: ${?KAFKA_BROKERS}

The configuration key "kafka.bootstrap.servers" references ${?KAFKA_BROKERS} but the
fallback value at "kafka.bootstrap.server" (note the typo) was not found.

Expected key path: kafka.bootstrap.servers
Actual fallback key: kafka.bootstrap.server (singular, missing 's')
```

## Service Health Status

```
Service           Status      Last Healthy    Error
---------         ------      ------------    -----
gateway           DOWN        02:14 UTC       ConfigException
auth              DOWN        02:14 UTC       ConfigException
documents         DOWN        02:14 UTC       Build failed
search            DOWN        02:14 UTC       Build failed
graph             DOWN        02:14 UTC       Build failed
embeddings        DOWN        02:14 UTC       Build failed
collab            DOWN        02:14 UTC       Build failed
billing           DOWN        02:14 UTC       Build failed
notifications     N/A         Never           Module not found
analytics         DOWN        02:14 UTC       Build failed
```

## Consul Initialization Logs

When services do manage to start:

```
2024-02-20T02:35:12.456Z [ERROR] Failed to initialize Consul client
io.ktor.client.plugins.ClientRequestException: Client request failed
    at com.mindvault.shared.discovery.ConsulClient.init(ConsulClient.kt:45)
    at com.mindvault.shared.discovery.ConsulClient.<init>(ConsulClient.kt:28)

Caused by: java.net.ConnectException: Connection refused (Connection refused)
    ... Consul was not ready when client initialized eagerly
```

## Kafka Producer Errors

After eventually getting services running:

```
2024-02-20T02:40:23.789Z [ERROR] Kafka producer failed to serialize event
org.apache.kafka.common.errors.SerializationException:
Error serializing message to topic 'document-events'

Caused by: java.lang.ClassCastException:
class [B cannot be cast to class java.lang.String
    at org.apache.kafka.common.serialization.StringSerializer.serialize(StringSerializer.java:28)

Event payload was serialized as JSON bytes but producer is configured with StringSerializer
Expected: ByteArraySerializer for JSON payload
Actual: StringSerializer
```

## Attempted Mitigations

1. **Cleared Gradle caches** - `rm -rf ~/.gradle/caches` - no change
2. **Rebuilt from fresh clone** - same failures
3. **Rolled back to previous commit** - different errors (regressions introduced)
4. **Manually started Consul before services** - helps with Consul error but other issues persist

## Questions for Investigation

1. Why is the Kotlin plugin not being found even though it's declared?
2. Why is the `notifications` module not being included in the build?
3. Why does the HOCON configuration have mismatched key names?
4. Why does the Consul client fail if Consul isn't immediately available?
5. Why is Kafka producer using wrong serializer for JSON events?

## Impact Assessment

- **Services Affected**: All 10 microservices
- **Users Affected**: All users (complete outage)
- **Revenue Impact**: $15,000/hour estimated (enterprise customers SLA breach)
- **Time to Resolution**: Unknown (root cause still under investigation)

## Related Changes

Recent commits in the past 24 hours:
- "Refactored Gradle configuration to use root plugins block"
- "Updated HOCON config for Kafka settings"
- "Added eager initialization for Consul client"
- "Cleaned up settings.gradle.kts"

---

**Status**: INVESTIGATING
**Assigned**: @platform-team
**Escalation Path**: VP Engineering notified at 03:00 UTC if not resolved
