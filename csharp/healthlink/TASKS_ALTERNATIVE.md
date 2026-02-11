# HealthLink - Alternative Task Specifications

This document provides alternative task specifications for the HealthLink healthcare platform. Each task is designed to exercise different software engineering competencies while remaining grounded in realistic healthcare domain requirements.

---

## Task 1: Feature Development - Patient Medical History Timeline

### Description

HealthLink's clinical staff need a comprehensive medical history timeline feature to support better patient care decisions. The current system stores patient appointments and documents but lacks a unified view that presents all patient interactions chronologically with relevant clinical context.

Implement a new `MedicalHistoryService` that aggregates patient data from multiple sources (appointments, documents, and a new clinical notes entity) into a unified timeline. The timeline should support filtering by date range, encounter type, and provider. Each timeline entry must include relevant metadata such as the attending physician, encounter duration, and associated diagnoses.

The feature must integrate with the existing `PatientService` and respect the platform's authentication and authorization patterns. Clinical notes should be properly encrypted at rest, and the timeline API must support pagination for patients with extensive medical histories.

### Acceptance Criteria

- A new `ClinicalNote` entity is added with fields for note content, encounter date, provider ID, note type (progress note, consultation, procedure note), and associated diagnosis codes
- The `MedicalHistoryService` provides methods to retrieve a paginated timeline combining appointments, documents, and clinical notes
- Timeline entries are sorted chronologically with configurable ascending/descending order
- Date range filtering supports both start and end date parameters with proper validation
- The service properly handles patients with no history (returns empty timeline, not null or error)
- All database operations use async patterns consistent with the existing codebase
- Authorization ensures users can only access timelines for patients they are permitted to view
- Unit tests cover timeline aggregation, filtering, pagination edge cases, and empty history scenarios

### Test Command

```bash
dotnet test --filter "FullyQualifiedName~MedicalHistoryService"
```

---

## Task 2: Refactoring - Consolidate Notification Delivery Channels

### Description

The current `NotificationService` was built with only email delivery in mind, but HealthLink now needs to support multiple notification channels including SMS, push notifications, and in-app messages. The existing implementation has tightly coupled SMTP logic that makes adding new channels difficult and violates the Open/Closed principle.

Refactor the notification subsystem to use a strategy pattern that allows notification channels to be added without modifying existing code. Each channel should be independently configurable and testable. The refactoring must preserve backward compatibility with existing email functionality while enabling the addition of SMS and push notification channels.

The refactored design should support channel fallback (e.g., try SMS first, fall back to email if SMS fails) and channel preferences per patient. Consider that some notifications (appointment reminders) should respect patient preferences while others (urgent clinical alerts) may need to use all available channels.

### Acceptance Criteria

- An `INotificationChannel` interface is extracted with methods for sending notifications and checking channel availability
- The existing SMTP email logic is encapsulated in an `EmailNotificationChannel` implementation
- A `NotificationDispatcher` orchestrates delivery across multiple channels based on notification priority and patient preferences
- Patient preferences for notification channels are persisted and respected for non-urgent notifications
- Channel fallback logic is implemented with configurable retry policies
- The circular dependency between `NotificationService` and `SchedulingService` is resolved as part of the refactoring
- All existing notification-related tests continue to pass without modification
- New tests verify channel selection logic, fallback behavior, and preference handling

### Test Command

```bash
dotnet test --filter "Namespace~HealthLink.Tests.Unit" --filter "FullyQualifiedName~Notification"
```

---

## Task 3: Performance Optimization - Appointment Query Efficiency

### Description

Performance monitoring has identified the appointment retrieval APIs as a bottleneck during peak clinic hours. The `AppointmentRepository` and `AppointmentService` execute multiple database queries that could be consolidated, and the current implementation pulls more data than necessary for common use cases like daily schedule views.

Optimize the appointment query path to reduce database round trips and minimize data transfer. The daily schedule endpoint, which shows all appointments for a specific date and provider, currently takes over 2 seconds during busy periods. The target is sub-200ms response time for a typical day with 40-60 appointments.

Analysis shows the current implementation suffers from N+1 query problems when loading patient details for appointment lists, inefficient date filtering that doesn't leverage database indexes, and unnecessary eager loading of related entities that aren't displayed in list views.

### Acceptance Criteria

- The `GetByStatusAsync` method is rewritten to filter at the database level instead of loading all appointments into memory
- A new `GetDailyScheduleAsync` method is added that returns a projection (DTO) with only the fields needed for schedule display
- N+1 queries are eliminated by using appropriate `Include` statements or explicit projections
- Database indexes are added for commonly filtered columns (date, provider ID, status)
- The `AsSplitQuery()` optimization is applied where cartesian explosion is detected
- Query execution time for daily schedules with 50 appointments is under 200ms (verifiable via test output)
- Read-only queries use `AsNoTracking()` to avoid change tracker overhead
- Integration tests verify the optimized queries return correct results

### Test Command

```bash
dotnet test --filter "FullyQualifiedName~AppointmentService" --verbosity normal
```

---

## Task 4: API Extension - Bulk Patient Operations

### Description

HealthLink's administrative users need bulk operation capabilities for patient management scenarios such as annual insurance eligibility updates, practice mergers requiring patient record transfers, and regulatory compliance requiring bulk consent status updates. The current API only supports single-patient operations, forcing administrators to make hundreds of individual API calls.

Extend the Patient API to support bulk operations including bulk status updates (activate/deactivate), bulk attribute modifications (insurance provider, primary care physician), and bulk export for data portability compliance. Each bulk operation must be atomic (all succeed or all fail) and provide detailed operation results.

The bulk operations must respect the platform's authorization model, ensuring users can only modify patients they have permission to access. Operations on large patient sets should provide progress feedback and support cancellation for long-running requests.

### Acceptance Criteria

- A new `BulkPatientController` endpoint accepts batch update requests with up to 1000 patient IDs per request
- Bulk operations are wrapped in database transactions to ensure atomicity
- The response includes per-patient success/failure status with error details for failures
- Validation errors (invalid patient ID, unauthorized access) are collected and returned without aborting the entire batch
- A bulk export endpoint generates CSV or JSON output for selected patients with configurable field selection
- Progress reporting is implemented for operations exceeding 100 patients
- Rate limiting prevents abuse of bulk endpoints
- Authorization validates access to each patient in the batch before processing

### Test Command

```bash
dotnet test --filter "FullyQualifiedName~BulkPatient"
```

---

## Task 5: Migration - Transition from In-Memory Cache to Redis

### Description

The current `CacheService` uses an in-memory dictionary that doesn't persist across application restarts and doesn't work in a multi-instance deployment scenario. HealthLink is moving to a Kubernetes deployment with multiple replicas, requiring a distributed caching solution.

Migrate the caching layer from the in-memory implementation to Redis using the StackExchange.Redis client that's already included in the project dependencies. The migration must be transparent to cache consumers, maintaining the existing `ICacheService` interface while switching to Redis as the backing store.

The migration should address the existing `ValueTask` double-await bug in the cache service and implement proper connection resilience for Redis including retry policies, circuit breaker patterns for Redis unavailability, and graceful degradation when the cache is unreachable. Cache key namespacing should be implemented to prevent collisions in shared Redis instances.

### Acceptance Criteria

- The `CacheService` implementation is replaced with a Redis-backed implementation using StackExchange.Redis
- The `ICacheService` interface remains unchanged, ensuring zero modifications to consuming code
- Connection string and configuration are externalized to appsettings.json using the IOptions pattern
- Retry policies handle transient Redis connection failures with exponential backoff
- A circuit breaker prevents cascading failures when Redis is unavailable, falling back to pass-through behavior
- Cache keys are prefixed with an application namespace to support shared Redis instances
- The `ValueTask` handling in `GetOrCreateAsync` is corrected to avoid double-await issues
- Integration tests verify correct behavior with Redis (using Testcontainers)
- Unit tests mock Redis connection to verify fallback behavior

### Test Command

```bash
dotnet test --filter "FullyQualifiedName~CacheService"
```
