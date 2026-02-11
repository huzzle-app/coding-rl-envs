# HealthLink - Greenfield Tasks

## Overview

HealthLink provides 3 greenfield implementation tasks that require building new services from scratch following existing architectural patterns. Each task exercises core competencies: service layer design, event-driven architecture, and external system integration. All implementations must follow the established async patterns, dependency injection conventions, and testing practices.

## Environment

- **Language**: C# 12 / .NET 8
- **Framework**: ASP.NET Core 8 (Minimal APIs + Controllers)
- **ORM**: Entity Framework Core 8 + Npgsql
- **Infrastructure**: PostgreSQL 16, Redis 7
- **Patterns**: MediatR, IOptions, Dependency Injection, async/await
- **Testing**: xUnit, FluentAssertions, Moq, Testcontainers
- **Difficulty**: Senior Engineer

## Tasks

### Task 1: Prescription Validation Service (Greenfield)

Implement a prescription validation service that ensures medication safety by validating prescriptions against patient allergies, drug interactions, and dosage limits. This is a critical patient safety feature.

**Interface Contract:**
```csharp
public interface IPrescriptionValidationService
{
    Task<PrescriptionValidationResult> ValidateAsync(
        int patientId, Prescription prescription, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<DrugInteraction>> CheckInteractionsAsync(
        int patientId, string drugCode, CancellationToken cancellationToken = default);
    DosageValidationResult ValidateDosage(Prescription prescription, int patientAge);
    Task<IReadOnlyList<string>> GetPatientAllergiesAsync(
        int patientId, CancellationToken cancellationToken = default);
}
```

**Key components:**
- `Prescription` entity with drug code, dosage, frequency, and duration
- `PatientAllergy` entity tracking allergen codes and severity
- `PrescriptionValidationResult` containing errors and warnings with severity levels
- `DrugInteraction` record describing drug-drug interactions with severity
- `DosageValidationResult` checking age-appropriate and daily limits
- Validation service caching drug interaction lookups via `ICacheService`
- Database integration points: `DbSet<Prescription>` and `DbSet<PatientAllergy>` in `HealthLinkDbContext`
- DI registration as scoped service in `Program.cs`

**Acceptance Criteria:**
- All interfaces implemented with proper async patterns (`ConfigureAwait(false)` in library code)
- Minimum 15 unit tests in `tests/HealthLink.Tests/Unit/PrescriptionValidationServiceTests.cs`
- Integration tests verifying database queries work correctly
- Proper null handling using defaults instead of `null!` suppression
- `IQueryable` usage in repository for SQL-level filtering
- Drug interaction lookup caching to avoid repeated database queries
- Thread-safe implementation without shared mutable state

**Test Command:** `dotnet test`

---

### Task 2: Appointment Reminder System (Greenfield)

Implement an automated appointment reminder system that schedules notifications at configurable intervals before appointments. The system must integrate with the existing `INotificationService` and handle concurrency correctly in background processing.

**Interface Contract:**
```csharp
public interface IAppointmentReminderService : IAsyncDisposable
{
    Task<IReadOnlyList<DateTime>> ScheduleRemindersAsync(
        int appointmentId, ReminderSettings? reminderSettings = null, CancellationToken cancellationToken = default);
    Task CancelRemindersAsync(int appointmentId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<PendingReminder>> GetPendingRemindersAsync(
        int patientId, CancellationToken cancellationToken = default);
    Task<int> ProcessDueRemindersAsync(int batchSize = 100, CancellationToken cancellationToken = default);
    Task UpdatePatientPreferencesAsync(
        int patientId, ReminderPreferences preferences, CancellationToken cancellationToken = default);
}
```

**Key components:**
- `PendingReminder` entity tracking scheduled reminders with status and retry count
- `ReminderSettings` record with hours-before-appointment and channel preferences
- `ReminderPreferences` entity storing patient notification channel preferences and quiet hours
- `ReminderBackgroundService : BackgroundService` processing due reminders in batches
- Enums for `ReminderChannel` (Email, Sms, Push), `ReminderStatus` (Pending, Sent, Failed, Cancelled)
- Integration with existing `INotificationService` for actual message delivery
- Database integration points: `DbSet<PendingReminder>` and `DbSet<ReminderPreferences>` in `HealthLinkDbContext`
- Event handler subscribing to `ISchedulingService.AppointmentScheduled` event

**Acceptance Criteria:**
- Implements `IAsyncDisposable` correctly with `await using` pattern
- Background service properly handles cancellation tokens
- No fire-and-forget tasks; all async operations awaited or properly observed
- Event handlers use `async Task` pattern (not `async void`)
- Minimum 20 unit tests in `tests/HealthLink.Tests/Unit/AppointmentReminderServiceTests.cs`
- Concurrency tests verifying thread-safe batch processing
- Proper event unsubscription in `DisposeAsync()` preventing memory leaks
- `AsNoTracking()` for read-only queries avoiding change tracker staleness

**Test Command:** `dotnet test`

---

### Task 3: Lab Results Integration Service (Greenfield)

Implement a service that integrates with external laboratory systems to fetch, store, and notify patients of lab results. Must properly use `IHttpClientFactory` for external calls and handle identifier mapping between systems.

**Interface Contract:**
```csharp
public interface ILabResultsService
{
    Task<IReadOnlyList<LabResult>> FetchPendingResultsAsync(
        string labSystemId, DateTime? since = null, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<LabResult>> GetPatientResultsAsync(
        int patientId, LabResultFilter? filter = null, CancellationToken cancellationToken = default);
    Task<LabResult?> GetByIdAsync(int resultId, CancellationToken cancellationToken = default);
    Task MarkAsReviewedAsync(
        int resultId, int reviewedByDoctorId, string? notes = null, CancellationToken cancellationToken = default);
    Task<bool> NotifyPatientAsync(int resultId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<LabResult>> GetCriticalPendingResultsAsync(CancellationToken cancellationToken = default);
}

public interface ILabResultRepository
{
    IQueryable<LabResult> GetQueryable();
    Task<LabResult?> GetByIdAsync(int id, CancellationToken cancellationToken = default);
    Task<LabResult?> GetByExternalIdAsync(
        string labSystemId, string externalResultId, CancellationToken cancellationToken = default);
    Task<LabResult> AddAsync(LabResult result, CancellationToken cancellationToken = default);
    Task UpdateAsync(LabResult result, CancellationToken cancellationToken = default);
}
```

**Key components:**
- `LabResult` entity with collection date, result date, test codes, numeric/text values, reference ranges, and critical flags
- `ResultFlag` enum (Normal, Low, High, CriticalLow, CriticalHigh, Abnormal)
- `LabResultStatus` enum (Pending, Preliminary, Final, Corrected, Cancelled)
- `LabResultFilter` record for parameterized queries with date range, category, and abnormal-only filters
- `ExternalLabResponse` and `ExternalLabResult` records mapping external lab system API responses
- `LabResultRepository : ILabResultRepository` returning `IQueryable<LabResult>` for SQL-level filtering
- `LabResultsController` with endpoints: `GET /api/labresults/patient/{patientId}`, `GET /api/labresults/{id}`, `POST /api/labresults/{id}/review`, `POST /api/labresults/{id}/notify`, `GET /api/labresults/critical`
- Integration with `IHttpClientFactory` for external API calls
- Caching reference data via `ICacheService`
- Patient notifications via existing `INotificationService`
- Database integration points: `DbSet<LabResult>` in `HealthLinkDbContext` with proper EF Core configuration

**Acceptance Criteria:**
- Uses `IHttpClientFactory.CreateClient()` for external API calls (not `new HttpClient()`)
- Proper error handling for external API failures with retry logic
- Repository returns `IQueryable<LabResult>` enabling SQL-level filtering
- Uses `AsNoTracking()` for read-only queries
- Proper patient identifier mapping between external system and internal IDs
- Minimum 18 unit tests in `tests/HealthLink.Tests/Unit/LabResultsServiceTests.cs`
- Security tests verifying patients can only access their own results
- Uses `ExecuteSqlInterpolated()` for any raw SQL (not `ExecuteSqlRaw()` with string interpolation)
- Controller uses proper async patterns (no `.Result` or `.Wait()`)
- EF Core configuration includes `HasMaxLength()` for string columns

**Test Command:** `dotnet test`

---

## Getting Started

```bash
# Start services
docker compose up -d

# Run tests for greenfield tasks
dotnet test
```

## Success Criteria

Implementation meets the interface contracts and acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). Tests verify correct service behavior, proper database integration, external system communication, and adherence to HealthLink's architectural patterns including async/await conventions, dependency injection, and entity framework usage.
