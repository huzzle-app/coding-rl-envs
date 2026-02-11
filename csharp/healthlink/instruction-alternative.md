# HealthLink - Alternative Tasks

## Overview

HealthLink's healthcare platform offers 5 alternative engineering tasks that extend the existing codebase with new features, refactor critical systems, and optimize performance bottlenecks. Each task exercises different competencies while following the established ASP.NET Core patterns and architectural guidelines.

## Environment

- **Language**: C# 12 / .NET 8
- **Framework**: ASP.NET Core 8 (Minimal APIs + Controllers)
- **ORM**: Entity Framework Core 8 + Npgsql
- **Infrastructure**: PostgreSQL 16, Redis 7
- **Patterns**: MediatR, IOptions, Dependency Injection
- **Testing**: xUnit, FluentAssertions, Moq, Testcontainers
- **Difficulty**: Senior Engineer

## Tasks

### Task 1: Feature Development - Patient Medical History Timeline (Feature)

Implement a comprehensive medical history timeline feature that aggregates patient data from multiple sources (appointments, documents, and clinical notes) into a unified chronological view. The timeline must support filtering by date range, encounter type, and provider, with pagination for patients with extensive histories.

**Key deliverables:**
- New `ClinicalNote` entity with note content, encounter date, provider ID, note type, and diagnosis codes
- `MedicalHistoryService` that retrieves paginated timelines combining appointments, documents, and clinical notes
- Chronological sorting with configurable ascending/descending order
- Date range filtering with proper validation
- Proper authorization ensuring users can only access permitted patient timelines

**Test Command:** `dotnet test --filter "FullyQualifiedName~MedicalHistoryService"`

---

### Task 2: Refactoring - Consolidate Notification Delivery Channels (Refactor)

Refactor the `NotificationService` to support multiple delivery channels (email, SMS, push notifications) using a strategy pattern. The refactoring preserves backward compatibility while enabling flexible channel configuration and fallback mechanisms.

**Key deliverables:**
- `INotificationChannel` interface for pluggable delivery strategies
- `EmailNotificationChannel` encapsulating existing SMTP logic
- `NotificationDispatcher` orchestrating multi-channel delivery
- Channel fallback logic with configurable retry policies
- Patient channel preferences persisted and respected for non-urgent notifications
- Resolution of circular dependency between `NotificationService` and `SchedulingService`

**Test Command:** `dotnet test --filter "Namespace~HealthLink.Tests.Unit" --filter "FullyQualifiedName~Notification"`

---

### Task 3: Performance Optimization - Appointment Query Efficiency (Optimize)

Optimize the appointment retrieval APIs that are experiencing bottlenecks during peak hours. Reduce database round trips from N+1 query problems, implement efficient date filtering with proper indexes, and achieve sub-200ms response times for daily schedule views.

**Key deliverables:**
- Rewrite `GetByStatusAsync` to filter at the database level
- New `GetDailyScheduleAsync` method returning DTOs with only necessary fields
- Elimination of N+1 queries using appropriate `Include` statements or projections
- Database indexes for commonly filtered columns (date, provider ID, status)
- Application of `AsSplitQuery()` optimization where cartesian explosion is detected
- Use of `AsNoTracking()` for read-only queries

**Test Command:** `dotnet test --filter "FullyQualifiedName~AppointmentService" --verbosity normal`

---

### Task 4: API Extension - Bulk Patient Operations (API)

Extend the Patient API with bulk operation capabilities for administrative scenarios such as insurance eligibility updates, practice mergers, and compliance tasks. Bulk operations must be atomic, respect authorization models, and provide detailed operation results.

**Key deliverables:**
- New `BulkPatientController` endpoint accepting batch updates with up to 1000 patient IDs
- Atomic database transactions ensuring all succeed or all fail
- Per-patient success/failure status with error details
- Validation error collection without aborting entire batch
- Bulk export endpoint generating CSV or JSON with configurable field selection
- Progress reporting for operations exceeding 100 patients
- Rate limiting and per-patient authorization validation

**Test Command:** `dotnet test --filter "FullyQualifiedName~BulkPatient"`

---

### Task 5: Migration - Transition from In-Memory Cache to Redis (Migration)

Migrate the caching layer from in-memory dictionary to Redis using StackExchange.Redis, maintaining the existing `ICacheService` interface while switching to a distributed backing store. Implement connection resilience, retry policies, and graceful degradation.

**Key deliverables:**
- Redis-backed `CacheService` implementation using StackExchange.Redis
- Unchanged `ICacheService` interface for transparent consumer migration
- Configuration externalized to appsettings.json using IOptions pattern
- Retry policies with exponential backoff for transient failures
- Circuit breaker pattern preventing cascading failures
- Cache key namespacing for shared Redis instances
- Correction of existing `ValueTask` double-await bug
- Integration tests using Testcontainers for Redis

**Test Command:** `dotnet test --filter "FullyQualifiedName~CacheService"`

---

## Getting Started

```bash
# Start services
docker compose up -d

# Run tests for alternative tasks
dotnet test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). Each task includes specific test commands for validation and integration tests verify correct behavior with actual infrastructure dependencies.
