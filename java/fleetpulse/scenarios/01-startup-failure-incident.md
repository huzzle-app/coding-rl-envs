# Incident Report: Fleet Services Won't Start

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-02-12 06:23 UTC
**Acknowledged**: 2024-02-12 06:28 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: fleetpulse-vehicles-prod deployment stuck in CrashLoopBackOff
Cluster: fleetpulse-prod-us-east-1
Namespace: fleet-services
Pods affected: 8/8 (all replicas)
Restart count: 47 (in last 30 minutes)
```

## Timeline

**06:23 UTC** - Initial alert: vehicles service pods entering CrashLoopBackOff

**06:28 UTC** - Alert acknowledged. Team notices auth, dispatch, and tracking services also failing

**06:35 UTC** - All 10 microservices now in crash loop or stuck initializing

**06:42 UTC** - Gateway pod shows this in logs before crash:
```
2024-02-12T06:42:18.234Z ERROR o.s.boot.SpringApplication - Application run failed
org.springframework.beans.factory.BeanCurrentlyInCreationException:
Error creating bean with name 'appConfig': Requested bean is currently in creation:
Is there an unresolvable circular reference?
    at o.s.b.f.support.DefaultSingletonBeanRegistry.beforeSingletonCreation
    at o.s.b.f.support.DefaultSingletonBeanRegistry.getSingleton
    ... 45 more
Caused by: org.springframework.beans.factory.BeanCurrentlyInCreationException:
Error creating bean with name 'eventBus': Requested bean is currently in creation
```

**06:48 UTC** - Attempted to scale down to single replica per service - still crashing

**06:55 UTC** - Reverted to previous deployment - SAME ERROR (this isn't a new bug)

## Application Logs from Crash

### Gateway Service
```
2024-02-12T06:42:15.001Z INFO  Starting FleetPulse Gateway on fleetpulse-gateway-6f8d7c9b5-x2k4m
2024-02-12T06:42:15.823Z INFO  Bootstrapping Spring Boot application
2024-02-12T06:42:17.456Z INFO  Loading application configuration...
2024-02-12T06:42:17.892Z DEBUG Creating bean 'appConfig'
2024-02-12T06:42:17.894Z DEBUG Creating bean 'eventBus'
2024-02-12T06:42:18.001Z DEBUG Bean 'eventBus' requires 'appConfig'
2024-02-12T06:42:18.003Z DEBUG Bean 'appConfig' requires 'eventBus'
2024-02-12T06:42:18.234Z ERROR BeanCurrentlyInCreationException: Circular reference detected
```

### Vehicles Service
```
2024-02-12T06:42:19.445Z INFO  Attempting to connect to Kafka broker kafka:9092
2024-02-12T06:42:24.445Z WARN  Kafka connection attempt 1 failed: UNKNOWN_TOPIC_OR_PARTITION
2024-02-12T06:42:29.445Z WARN  Kafka connection attempt 2 failed: UNKNOWN_TOPIC_OR_PARTITION
2024-02-12T06:42:34.445Z WARN  Kafka connection attempt 3 failed: UNKNOWN_TOPIC_OR_PARTITION
2024-02-12T06:42:39.445Z ERROR Failed to subscribe to topic 'vehicle-telemetry': The topic does not exist
org.apache.kafka.common.errors.UnknownTopicOrPartitionException:
This server does not host this topic-partition.
```

### Shared Library (seen in multiple services)
```
2024-02-12T06:42:16.112Z INFO  Loading Consul configuration from consul:8500
2024-02-12T06:42:16.345Z WARN  Failed to load config from Consul: connection refused
2024-02-12T06:42:16.346Z INFO  Falling back to local properties...
2024-02-12T06:42:16.567Z ERROR Missing required property: fleet.database.url
2024-02-12T06:42:16.568Z ERROR Missing required property: fleet.kafka.bootstrap-servers
2024-02-12T06:42:16.569Z ERROR Missing required property: fleet.redis.host
java.lang.IllegalStateException: Could not resolve placeholder 'fleet.database.url' in value "${fleet.database.url}"
```

## Kubernetes Events

```
$ kubectl get events --namespace=fleet-services --sort-by='.lastTimestamp'

LAST SEEN   TYPE      REASON          OBJECT                           MESSAGE
2m          Warning   BackOff         pod/fleetpulse-gateway-xxx       Back-off restarting failed container
2m          Warning   BackOff         pod/fleetpulse-vehicles-xxx      Back-off restarting failed container
3m          Warning   FailedCreate    pod/fleetpulse-auth-xxx          Error creating container: exit code 1
3m          Normal    Pulled          pod/fleetpulse-dispatch-xxx      Container image already present
4m          Warning   BackOff         pod/fleetpulse-tracking-xxx      Back-off restarting failed container
```

## Infrastructure Status

| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL | Healthy | All 3 databases accessible |
| Kafka | Healthy | Broker responding, but topic list empty |
| Redis | Healthy | Cluster mode, 6 nodes |
| Consul | Healthy | KV store accessible via UI |

## Attempted Fixes

1. **Restarted all pods** - No change, same errors on startup
2. **Increased startup timeout** - Pods just crash later with same error
3. **Manually created Kafka topics** - Some services got further, but still failed on circular deps
4. **Checked Consul KV store** - Config values exist but services can't read them

## Customer Impact

- **Complete outage** - No fleet management functionality available
- Real-time tracking dashboard shows "Service Unavailable"
- Dispatch operations halted - drivers cannot receive assignments
- Mobile app showing connection errors

## Questions for Investigation

1. How did this ever work? Did a recent Spring Boot upgrade break something?
2. Why are Kafka topics not auto-created? They were before.
3. Why is Consul config not being loaded? The values are in the KV store.
4. Is there a classpath issue? We're seeing some `NoSuchMethodError` intermittently:
   ```
   java.lang.NoSuchMethodError: 'com.fasterxml.jackson.databind.ObjectMapper
   com.fasterxml.jackson.databind.ObjectMapper.registerModules()'
   ```

## Files to Investigate

Based on error messages, focus on:
- `shared/src/main/java/com/fleetpulse/shared/config/AppConfig.java`
- `shared/src/main/java/com/fleetpulse/shared/events/EventBus.java`
- `shared/src/main/resources/bootstrap.yml`
- `pom.xml` (parent and shared module)

---

**Status**: CRITICAL - ALL SERVICES DOWN
**Assigned**: @platform-team
**Escalation**: VP of Engineering notified at 07:00 UTC
