# Incident Report: Application Fails to Start

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-18 02:15 UTC
**Acknowledged**: 2024-01-18 02:18 UTC
**Team**: Platform Engineering

---

## Alert Details

```
CRITICAL: docuvault-api-prod deployment failing
Cluster: docuvault-prod-us-east-1
Deployment: docuvault-api
Replicas Ready: 0/3
Event: CrashLoopBackOff
```

## Timeline

**02:15 UTC** - Deployment started for docuvault-api v2.4.1

**02:16 UTC** - First pod enters CrashLoopBackOff

**02:17 UTC** - All 3 pods failing with identical error

**02:18 UTC** - On-call engineer paged

**02:25 UTC** - Rollback initiated to v2.4.0

**02:28 UTC** - v2.4.0 stable, but new features not deployed

## Application Logs

### Pod 1 Startup Failure

```
2024-01-18T02:16:01.234Z  INFO  Starting DocuVaultApplication v2.4.1 using Java 21
2024-01-18T02:16:01.456Z  INFO  The following 1 profile is active: "prod"
2024-01-18T02:16:02.789Z  INFO  Bootstrapping Spring Data JPA repositories
2024-01-18T02:16:03.012Z  INFO  Finished Spring Data repository scanning in 223ms
2024-01-18T02:16:05.345Z ERROR  Error creating bean with name 'documentService'
2024-01-18T02:16:05.346Z ERROR  Requested bean is currently in creation: Is there an unresolvable circular reference?

org.springframework.beans.factory.BeanCurrentlyInCreationException:
Error creating bean with name 'documentService': Requested bean is currently in creation:
Is there an unresolvable circular reference?

    at o.s.beans.factory.support.DefaultSingletonBeanRegistry.beforeSingletonCreation(DefaultSingletonBeanRegistry.java:355)
    at o.s.beans.factory.support.DefaultSingletonBeanRegistry.getSingleton(DefaultSingletonBeanRegistry.java:227)
    at o.s.beans.factory.support.AbstractBeanFactory.doGetBean(AbstractBeanFactory.java:333)
    at o.s.beans.factory.support.AbstractBeanFactory.getBean(AbstractBeanFactory.java:208)
    at o.s.beans.factory.config.DependencyDescriptor.resolveCandidate(DependencyDescriptor.java:276)
    at o.s.beans.factory.support.DefaultListableBeanFactory.doResolveDependency(DefaultListableBeanFactory.java:1389)
    at o.s.beans.factory.support.DefaultListableBeanFactory.resolveDependency(DefaultListableBeanFactory.java:1309)
    at o.s.beans.factory.annotation.AutowiredAnnotationBeanPostProcessor$AutowiredFieldElement.resolveFieldValue(AutowiredAnnotationBeanPostProcessor.java:656)
```

### Circular Dependency Chain

```
Caused by: org.springframework.beans.factory.UnsatisfiedDependencyException:
Error creating bean with name 'notificationService' defined in file
[/app/BOOT-INF/classes/com/docuvault/service/NotificationService.class]:
Unsatisfied dependency expressed through constructor parameter 0;
nested exception is org.springframework.beans.factory.BeanCurrentlyInCreationException:
Error creating bean with name 'documentService': Requested bean is currently in creation

Bean dependency chain:
  documentService
    -> notificationService
      -> documentService  <-- CIRCULAR!
```

---

## Second Startup Attempt (After Commenting Out Circular Dependency)

After engineering attempted a hotfix by commenting out one injection, a new error appeared:

```
2024-01-18T03:45:12.123Z ERROR  Error creating bean with name 'documentController'
2024-01-18T03:45:12.124Z ERROR  Bean 'metadataExtractor' not found

org.springframework.beans.factory.NoSuchBeanDefinitionException:
No qualifying bean of type 'com.docuvault.util.MetadataExtractor' available:
expected at least 1 bean which qualifies as autowire candidate.
Dependency annotations: {@org.springframework.beans.factory.annotation.Autowired(required=true)}

    at o.s.beans.factory.support.DefaultListableBeanFactory.raiseNoMatchingBeanFound(DefaultListableBeanFactory.java:1801)
    at o.s.beans.factory.support.DefaultListableBeanFactory.doResolveDependency(DefaultListableBeanFactory.java:1357)
```

Investigation showed `MetadataExtractor` has `@Profile("prod")` but tests run under the `test` profile.

---

## Third Startup Attempt (After Profile Fix)

```
2024-01-18T04:12:33.456Z ERROR  Failed to bind properties under 'docuvault.max-file-size'

org.springframework.boot.context.properties.bind.BindException:
Failed to bind properties under 'docuvault.max-file-size' to java.lang.Long

Caused by: org.springframework.core.convert.ConverterNotFoundException:
No converter found capable of converting from type [java.lang.String] to type [java.lang.Long]

Property value: "10MB"
Expected type: java.lang.Long
```

The application.yml contains:
```yaml
docuvault:
  max-file-size: "10MB"
```

And the config class has:
```java
@Value("${docuvault.max-file-size}")
private long maxFileSize;
```

---

## Fourth Issue: Jackson Version Conflict

```
2024-01-18T05:30:15.789Z  WARN  Multiple versions of jackson-databind detected on classpath
2024-01-18T05:30:15.901Z ERROR  Failed to instantiate ObjectMapper

java.lang.NoSuchMethodError:
'com.fasterxml.jackson.databind.cfg.MutableCoercionConfig
com.fasterxml.jackson.databind.cfg.MapperConfig.coercionConfigDefaults()'

    at o.s.http.converter.json.Jackson2ObjectMapperBuilder.configure(Jackson2ObjectMapperBuilder.java:652)
```

Dependency tree shows conflict:
```
[INFO] +- com.fasterxml.jackson.core:jackson-databind:jar:2.13.0:compile
[INFO] |  \- com.fasterxml.jackson.core:jackson-core:jar:2.13.0:compile
[INFO] +- org.springframework.boot:spring-boot-starter-web:jar:3.2.0:compile
[INFO] |  +- com.fasterxml.jackson.core:jackson-databind:jar:2.15.3:compile (version managed from 2.13.0)
```

---

## Customer Impact

- **Duration**: 4 hours of attempted fixes
- **Result**: Rolled back to v2.4.0, new features delayed
- **Affected Services**: All DocuVault API endpoints
- **User Reports**: "Service unavailable" errors during deployment window

---

## Questions for Investigation

1. How do we break the circular dependency between DocumentService and NotificationService?
2. Should MetadataExtractor be available in all profiles or just production?
3. How should we handle the "10MB" string-to-long conversion for max file size?
4. Should we remove the explicit Jackson version from pom.xml and use Spring Boot's managed version?

---

## Files to Investigate

Based on stack traces:
- `src/main/java/com/docuvault/service/DocumentService.java`
- `src/main/java/com/docuvault/service/NotificationService.java`
- `src/main/java/com/docuvault/config/AppConfig.java`
- `src/main/java/com/docuvault/util/MetadataExtractor.java`
- `src/main/resources/application.yml`
- `pom.xml`

---

**Status**: INVESTIGATING
**Assigned**: @platform-team
**Follow-up**: Post-incident review scheduled for 2024-01-19 10:00 UTC
