# HealthLink Greenfield Tasks

These tasks require implementing NEW modules from scratch following HealthLink's existing architectural patterns. Each task defines interfaces, required classes, and acceptance criteria.

**Test Command:** `dotnet test`

---

## Task 1: Prescription Validation Service

### Overview

Implement a prescription validation service that validates medication prescriptions against patient allergies, drug interactions, and dosage limits. This is a critical safety feature for the healthcare platform.

### Interface Contract

Create the file: `src/HealthLink.Api/Services/PrescriptionValidationService.cs`

```csharp
using HealthLink.Api.Models;

namespace HealthLink.Api.Services;

/// <summary>
/// Service for validating medication prescriptions against safety rules.
/// </summary>
public interface IPrescriptionValidationService
{
    /// <summary>
    /// Validates a prescription against patient allergies, drug interactions, and dosage limits.
    /// </summary>
    /// <param name="patientId">The patient receiving the prescription.</param>
    /// <param name="prescription">The prescription to validate.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>A validation result containing any warnings or errors.</returns>
    Task<PrescriptionValidationResult> ValidateAsync(
        int patientId,
        Prescription prescription,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Checks if a specific drug has known interactions with the patient's current medications.
    /// </summary>
    /// <param name="patientId">The patient to check.</param>
    /// <param name="drugCode">The NDC (National Drug Code) of the drug to check.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of drug interactions found.</returns>
    Task<IReadOnlyList<DrugInteraction>> CheckInteractionsAsync(
        int patientId,
        string drugCode,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Validates dosage against age-appropriate limits and maximum daily dosage.
    /// </summary>
    /// <param name="prescription">The prescription to validate.</param>
    /// <param name="patientAge">Patient's age in years.</param>
    /// <returns>Dosage validation result with any violations.</returns>
    DosageValidationResult ValidateDosage(Prescription prescription, int patientAge);

    /// <summary>
    /// Gets the patient's known allergies for drug screening.
    /// </summary>
    /// <param name="patientId">The patient ID.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of allergen codes the patient is allergic to.</returns>
    Task<IReadOnlyList<string>> GetPatientAllergiesAsync(
        int patientId,
        CancellationToken cancellationToken = default);
}
```

### Required Models

Create the file: `src/HealthLink.Api/Models/Prescription.cs`

```csharp
namespace HealthLink.Api.Models;

/// <summary>
/// Represents a medication prescription.
/// </summary>
public class Prescription
{
    public int Id { get; set; }
    public int PatientId { get; set; }
    public int PrescriberDoctorId { get; set; }

    /// <summary>
    /// National Drug Code (NDC) for the medication.
    /// </summary>
    public string DrugCode { get; set; } = "";

    /// <summary>
    /// Drug name for display purposes.
    /// </summary>
    public string DrugName { get; set; } = "";

    /// <summary>
    /// Dosage amount (e.g., 500 for 500mg).
    /// </summary>
    public decimal DosageAmount { get; set; }

    /// <summary>
    /// Dosage unit (mg, ml, etc.).
    /// </summary>
    public string DosageUnit { get; set; } = "mg";

    /// <summary>
    /// Frequency of doses per day.
    /// </summary>
    public int FrequencyPerDay { get; set; }

    /// <summary>
    /// Duration of prescription in days.
    /// </summary>
    public int DurationDays { get; set; }

    /// <summary>
    /// Number of refills allowed.
    /// </summary>
    public int RefillsAllowed { get; set; }

    public DateTime PrescribedDate { get; set; }
    public DateTime? ExpirationDate { get; set; }
    public PrescriptionStatus Status { get; set; }

    public Patient Patient { get; set; } = null!;
}

public enum PrescriptionStatus
{
    Pending,
    Active,
    Filled,
    Expired,
    Cancelled
}

/// <summary>
/// Result of prescription validation.
/// </summary>
public record PrescriptionValidationResult
{
    public bool IsValid { get; init; }
    public IReadOnlyList<ValidationIssue> Errors { get; init; } = Array.Empty<ValidationIssue>();
    public IReadOnlyList<ValidationIssue> Warnings { get; init; } = Array.Empty<ValidationIssue>();
}

public record ValidationIssue(string Code, string Message, ValidationSeverity Severity);

public enum ValidationSeverity
{
    Info,
    Warning,
    Error,
    Critical
}

/// <summary>
/// Represents a drug-drug interaction.
/// </summary>
public record DrugInteraction
{
    public string Drug1Code { get; init; } = "";
    public string Drug2Code { get; init; } = "";
    public string Drug1Name { get; init; } = "";
    public string Drug2Name { get; init; } = "";
    public InteractionSeverity Severity { get; init; }
    public string Description { get; init; } = "";
}

public enum InteractionSeverity
{
    Minor,
    Moderate,
    Major,
    Contraindicated
}

/// <summary>
/// Result of dosage validation.
/// </summary>
public record DosageValidationResult
{
    public bool IsWithinLimits { get; init; }
    public decimal MaxDailyDosage { get; init; }
    public decimal RequestedDailyDosage { get; init; }
    public string? ViolationReason { get; init; }
}

/// <summary>
/// Patient allergy record.
/// </summary>
public class PatientAllergy
{
    public int Id { get; set; }
    public int PatientId { get; set; }
    public string AllergenCode { get; set; } = "";
    public string AllergenName { get; set; } = "";
    public AllergySeverity Severity { get; set; }
    public string? Reaction { get; set; }
    public DateTime RecordedDate { get; set; }

    public Patient Patient { get; set; } = null!;
}

public enum AllergySeverity
{
    Mild,
    Moderate,
    Severe,
    LifeThreatening
}
```

### Integration Points

1. **Database:** Add `DbSet<Prescription>` and `DbSet<PatientAllergy>` to `HealthLinkDbContext`
2. **DI Registration:** Register `IPrescriptionValidationService` as scoped in `Program.cs`
3. **Controller:** Create `PrescriptionController` with endpoints for validation

### Acceptance Criteria

- [ ] All interfaces implemented with proper async patterns (use `ConfigureAwait(false)` in library code)
- [ ] Unit tests in `tests/HealthLink.Tests/Unit/PrescriptionValidationServiceTests.cs` (minimum 15 tests)
- [ ] Integration tests that verify database queries work correctly
- [ ] Proper null handling (avoid `null!` suppression - use proper defaults or nullable types)
- [ ] Use `IQueryable` from repository to allow SQL-level filtering
- [ ] Cache drug interaction lookups using `ICacheService` to avoid repeated DB queries
- [ ] Thread-safe implementation (no shared mutable state without synchronization)

---

## Task 2: Appointment Reminder System

### Overview

Implement an automated appointment reminder system that sends notifications at configurable intervals before appointments. Must integrate with the existing `INotificationService` and handle scheduling correctly.

### Interface Contract

Create the file: `src/HealthLink.Api/Services/AppointmentReminderService.cs`

```csharp
using HealthLink.Api.Models;

namespace HealthLink.Api.Services;

/// <summary>
/// Service for scheduling and sending appointment reminders.
/// </summary>
public interface IAppointmentReminderService : IAsyncDisposable
{
    /// <summary>
    /// Schedules reminders for an appointment at configured intervals.
    /// </summary>
    /// <param name="appointmentId">The appointment to schedule reminders for.</param>
    /// <param name="reminderSettings">Optional custom reminder settings.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of scheduled reminder times.</returns>
    Task<IReadOnlyList<DateTime>> ScheduleRemindersAsync(
        int appointmentId,
        ReminderSettings? reminderSettings = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Cancels all pending reminders for an appointment.
    /// </summary>
    /// <param name="appointmentId">The appointment whose reminders should be cancelled.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task CancelRemindersAsync(int appointmentId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets all pending reminders for a patient.
    /// </summary>
    /// <param name="patientId">The patient ID.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of pending reminders.</returns>
    Task<IReadOnlyList<PendingReminder>> GetPendingRemindersAsync(
        int patientId,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Processes due reminders and sends notifications.
    /// This method should be called by a background service.
    /// </summary>
    /// <param name="batchSize">Maximum number of reminders to process in one batch.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>Number of reminders processed.</returns>
    Task<int> ProcessDueRemindersAsync(int batchSize = 100, CancellationToken cancellationToken = default);

    /// <summary>
    /// Updates reminder preferences for a patient.
    /// </summary>
    /// <param name="patientId">The patient ID.</param>
    /// <param name="preferences">New reminder preferences.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task UpdatePatientPreferencesAsync(
        int patientId,
        ReminderPreferences preferences,
        CancellationToken cancellationToken = default);
}
```

### Required Models

Create the file: `src/HealthLink.Api/Models/Reminder.cs`

```csharp
namespace HealthLink.Api.Models;

/// <summary>
/// Settings for scheduling reminders.
/// </summary>
public record ReminderSettings
{
    /// <summary>
    /// Hours before appointment to send reminders.
    /// Default: 24 hours and 2 hours before.
    /// </summary>
    public IReadOnlyList<int> HoursBeforeAppointment { get; init; } = new[] { 24, 2 };

    /// <summary>
    /// Whether to send SMS reminders.
    /// </summary>
    public bool SendSms { get; init; } = true;

    /// <summary>
    /// Whether to send email reminders.
    /// </summary>
    public bool SendEmail { get; init; } = true;

    /// <summary>
    /// Whether to send push notifications.
    /// </summary>
    public bool SendPush { get; init; } = false;
}

/// <summary>
/// A scheduled reminder awaiting delivery.
/// </summary>
public class PendingReminder
{
    public int Id { get; set; }
    public int AppointmentId { get; set; }
    public int PatientId { get; set; }
    public DateTime ScheduledTime { get; set; }
    public DateTime AppointmentTime { get; set; }
    public ReminderChannel Channel { get; set; }
    public ReminderStatus Status { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime? SentAt { get; set; }
    public int RetryCount { get; set; }
    public string? LastError { get; set; }

    public Appointment Appointment { get; set; } = null!;
    public Patient Patient { get; set; } = null!;
}

public enum ReminderChannel
{
    Email,
    Sms,
    Push
}

public enum ReminderStatus
{
    Pending,
    Sent,
    Failed,
    Cancelled
}

/// <summary>
/// Patient preferences for receiving reminders.
/// </summary>
public class ReminderPreferences
{
    public int Id { get; set; }
    public int PatientId { get; set; }
    public bool EmailEnabled { get; set; } = true;
    public bool SmsEnabled { get; set; } = true;
    public bool PushEnabled { get; set; } = false;

    /// <summary>
    /// Quiet hours start (hour of day, 0-23).
    /// </summary>
    public int? QuietHoursStart { get; set; }

    /// <summary>
    /// Quiet hours end (hour of day, 0-23).
    /// </summary>
    public int? QuietHoursEnd { get; set; }

    /// <summary>
    /// Preferred reminder times before appointments (hours).
    /// </summary>
    public IReadOnlyList<int> PreferredReminderHours { get; set; } = new[] { 24, 2 };

    public Patient Patient { get; set; } = null!;
}
```

### Background Service

Create the file: `src/HealthLink.Api/Services/ReminderBackgroundService.cs`

```csharp
namespace HealthLink.Api.Services;

/// <summary>
/// Background service that processes due reminders.
/// Must properly handle cancellation and implement IAsyncDisposable.
/// </summary>
public class ReminderBackgroundService : BackgroundService
{
    // Implementation required
}
```

### Integration Points

1. **Database:** Add `DbSet<PendingReminder>` and `DbSet<ReminderPreferences>` to `HealthLinkDbContext`
2. **DI Registration:** Register both `IAppointmentReminderService` and `ReminderBackgroundService`
3. **Notification Integration:** Use existing `INotificationService` for actual message delivery
4. **Scheduling Integration:** Hook into `ISchedulingService.AppointmentScheduled` event to auto-schedule reminders

### Acceptance Criteria

- [ ] Implements `IAsyncDisposable` correctly with `await using` pattern
- [ ] Background service properly handles cancellation tokens
- [ ] No fire-and-forget tasks - all async operations must be awaited or properly observed
- [ ] Event handlers use `async Task` pattern (not `async void`)
- [ ] Unit tests in `tests/HealthLink.Tests/Unit/AppointmentReminderServiceTests.cs` (minimum 20 tests)
- [ ] Concurrency tests verifying thread-safe batch processing
- [ ] Proper unsubscription from events in `DisposeAsync` to prevent memory leaks
- [ ] Uses `AsNoTracking()` for read-only queries to avoid change tracker staleness

---

## Task 3: Lab Results Integration Service

### Overview

Implement a service that integrates with external laboratory systems to fetch, store, and notify patients of their lab results. Must handle external API calls properly using `IHttpClientFactory`.

### Interface Contract

Create the file: `src/HealthLink.Api/Services/LabResultsService.cs`

```csharp
using HealthLink.Api.Models;

namespace HealthLink.Api.Services;

/// <summary>
/// Service for managing lab results from external laboratory systems.
/// </summary>
public interface ILabResultsService
{
    /// <summary>
    /// Fetches pending lab results from external lab system.
    /// </summary>
    /// <param name="labSystemId">Identifier of the lab system to query.</param>
    /// <param name="since">Only fetch results newer than this timestamp.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of lab results fetched.</returns>
    Task<IReadOnlyList<LabResult>> FetchPendingResultsAsync(
        string labSystemId,
        DateTime? since = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets lab results for a specific patient.
    /// </summary>
    /// <param name="patientId">The patient ID.</param>
    /// <param name="filter">Optional filter criteria.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of lab results matching criteria.</returns>
    Task<IReadOnlyList<LabResult>> GetPatientResultsAsync(
        int patientId,
        LabResultFilter? filter = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets a specific lab result by ID.
    /// </summary>
    /// <param name="resultId">The lab result ID.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The lab result or null if not found.</returns>
    Task<LabResult?> GetByIdAsync(int resultId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Marks a lab result as reviewed by the ordering physician.
    /// </summary>
    /// <param name="resultId">The lab result ID.</param>
    /// <param name="reviewedByDoctorId">The reviewing doctor's ID.</param>
    /// <param name="notes">Optional review notes.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    Task MarkAsReviewedAsync(
        int resultId,
        int reviewedByDoctorId,
        string? notes = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Notifies patient of available lab results.
    /// </summary>
    /// <param name="resultId">The lab result ID.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>True if notification was sent successfully.</returns>
    Task<bool> NotifyPatientAsync(int resultId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Checks if any critical results require immediate attention.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>List of critical results pending review.</returns>
    Task<IReadOnlyList<LabResult>> GetCriticalPendingResultsAsync(
        CancellationToken cancellationToken = default);
}
```

### Required Models

Create the file: `src/HealthLink.Api/Models/LabResult.cs`

```csharp
namespace HealthLink.Api.Models;

/// <summary>
/// Represents a lab test result.
/// </summary>
public class LabResult
{
    public int Id { get; set; }
    public int PatientId { get; set; }
    public int? OrderingDoctorId { get; set; }

    /// <summary>
    /// External lab system identifier.
    /// </summary>
    public string LabSystemId { get; set; } = "";

    /// <summary>
    /// External result reference number.
    /// </summary>
    public string ExternalResultId { get; set; } = "";

    /// <summary>
    /// LOINC code for the test.
    /// </summary>
    public string TestCode { get; set; } = "";

    /// <summary>
    /// Human-readable test name.
    /// </summary>
    public string TestName { get; set; } = "";

    /// <summary>
    /// Test category (e.g., "Chemistry", "Hematology", "Microbiology").
    /// </summary>
    public string Category { get; set; } = "";

    /// <summary>
    /// Numeric result value (if applicable).
    /// </summary>
    public decimal? NumericValue { get; set; }

    /// <summary>
    /// Text result (for non-numeric results).
    /// </summary>
    public string? TextValue { get; set; }

    /// <summary>
    /// Unit of measurement.
    /// </summary>
    public string? Unit { get; set; }

    /// <summary>
    /// Reference range for normal values.
    /// </summary>
    public string? ReferenceRange { get; set; }

    /// <summary>
    /// Whether the result is outside normal range.
    /// </summary>
    public ResultFlag Flag { get; set; }

    /// <summary>
    /// Whether this is a critical value requiring immediate attention.
    /// </summary>
    public bool IsCritical { get; set; }

    public DateTime CollectionDate { get; set; }
    public DateTime ResultDate { get; set; }
    public DateTime ReceivedDate { get; set; }

    public LabResultStatus Status { get; set; }
    public int? ReviewedByDoctorId { get; set; }
    public DateTime? ReviewedDate { get; set; }
    public string? ReviewNotes { get; set; }

    public bool PatientNotified { get; set; }
    public DateTime? PatientNotifiedDate { get; set; }

    public Patient Patient { get; set; } = null!;
}

public enum ResultFlag
{
    Normal,
    Low,
    High,
    CriticalLow,
    CriticalHigh,
    Abnormal
}

public enum LabResultStatus
{
    Pending,
    Preliminary,
    Final,
    Corrected,
    Cancelled
}

/// <summary>
/// Filter criteria for lab result queries.
/// </summary>
public record LabResultFilter
{
    public DateTime? FromDate { get; init; }
    public DateTime? ToDate { get; init; }
    public string? Category { get; init; }
    public string? TestCode { get; init; }
    public bool? OnlyAbnormal { get; init; }
    public bool? OnlyUnreviewed { get; init; }
    public bool? OnlyCritical { get; init; }
    public int? PageSize { get; init; } = 50;
    public int? PageNumber { get; init; } = 1;
}

/// <summary>
/// Response from external lab system API.
/// </summary>
public record ExternalLabResponse
{
    public bool Success { get; init; }
    public string? ErrorMessage { get; init; }
    public IReadOnlyList<ExternalLabResult> Results { get; init; } = Array.Empty<ExternalLabResult>();
}

public record ExternalLabResult
{
    public string ResultId { get; init; } = "";
    public string PatientIdentifier { get; init; } = "";
    public string TestCode { get; init; } = "";
    public string TestName { get; init; } = "";
    public string Value { get; init; } = "";
    public string? Unit { get; init; }
    public string? ReferenceRange { get; init; }
    public string? Flag { get; init; }
    public DateTime CollectionDateTime { get; init; }
    public DateTime ResultDateTime { get; init; }
    public string Status { get; init; } = "";
}
```

### Repository Interface

Create the file: `src/HealthLink.Api/Repositories/LabResultRepository.cs`

```csharp
using HealthLink.Api.Models;

namespace HealthLink.Api.Repositories;

/// <summary>
/// Repository for lab result data access.
/// Should return IQueryable to enable SQL-level filtering.
/// </summary>
public interface ILabResultRepository
{
    /// <summary>
    /// Gets lab results as IQueryable for further filtering.
    /// </summary>
    IQueryable<LabResult> GetQueryable();

    /// <summary>
    /// Gets a lab result by ID.
    /// </summary>
    Task<LabResult?> GetByIdAsync(int id, CancellationToken cancellationToken = default);

    /// <summary>
    /// Gets a lab result by external ID.
    /// </summary>
    Task<LabResult?> GetByExternalIdAsync(
        string labSystemId,
        string externalResultId,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Adds a new lab result.
    /// </summary>
    Task<LabResult> AddAsync(LabResult result, CancellationToken cancellationToken = default);

    /// <summary>
    /// Updates an existing lab result.
    /// </summary>
    Task UpdateAsync(LabResult result, CancellationToken cancellationToken = default);
}
```

### Integration Points

1. **Database:** Add `DbSet<LabResult>` to `HealthLinkDbContext` with proper EF Core configuration
2. **DI Registration:** Register `ILabResultsService` and `ILabResultRepository` as scoped
3. **HTTP Client:** Use `IHttpClientFactory` to create HTTP clients for external lab APIs (avoid `new HttpClient()`)
4. **Caching:** Cache frequently accessed reference data using `ICacheService`
5. **Notifications:** Use existing `INotificationService` for patient notifications

### Controller Endpoints

Create the file: `src/HealthLink.Api/Controllers/LabResultsController.cs`

Required endpoints:
- `GET /api/labresults/patient/{patientId}` - Get patient's lab results
- `GET /api/labresults/{id}` - Get specific lab result
- `POST /api/labresults/{id}/review` - Mark as reviewed by doctor
- `POST /api/labresults/{id}/notify` - Notify patient of result
- `GET /api/labresults/critical` - Get pending critical results

### Acceptance Criteria

- [ ] Uses `IHttpClientFactory.CreateClient()` for external API calls (not `new HttpClient()`)
- [ ] Proper error handling for external API failures with retry logic
- [ ] Repository returns `IQueryable<LabResult>` to enable SQL-level filtering
- [ ] Uses `AsNoTracking()` for read-only queries
- [ ] Properly handles patient identifier mapping between external system and internal IDs
- [ ] Unit tests in `tests/HealthLink.Tests/Unit/LabResultsServiceTests.cs` (minimum 18 tests)
- [ ] Security tests verifying patients can only access their own results
- [ ] Uses `ExecuteSqlInterpolated()` if any raw SQL is needed (not `ExecuteSqlRaw()` with interpolation)
- [ ] Controller uses proper async patterns (no `.Result` or `.Wait()`)
- [ ] EF Core configuration includes `HasMaxLength()` for string columns

---

## Architecture Guidelines

When implementing these tasks, follow the existing HealthLink patterns:

### Service Registration

```csharp
// In Program.cs - use AddScoped for DbContext-dependent services
builder.Services.AddScoped<IPrescriptionValidationService, PrescriptionValidationService>();
builder.Services.AddScoped<IAppointmentReminderService, AppointmentReminderService>();
builder.Services.AddScoped<ILabResultsService, LabResultsService>();
```

### Async Patterns

```csharp
// DO: Use async/await properly
public async Task<Result> GetDataAsync(CancellationToken ct)
{
    return await _context.Items
        .AsNoTracking()
        .Where(x => x.Active)
        .ToListAsync(ct)
        .ConfigureAwait(false);  // Use in library code
}

// DON'T: Never use .Result or .Wait()
public IActionResult GetData()
{
    var result = _service.GetDataAsync().Result; // DEADLOCK RISK!
}
```

### IDisposable Pattern

```csharp
// For services with resources to clean up
public class MyService : IAsyncDisposable
{
    public async ValueTask DisposeAsync()
    {
        // Unsubscribe from events
        _schedulingService.AppointmentScheduled -= OnAppointmentScheduled;

        // Dispose async resources
        await _asyncResource.DisposeAsync();
    }
}
```

### Repository Pattern

```csharp
// Return IQueryable to allow SQL-level filtering
public IQueryable<Entity> GetQueryable()
{
    return _context.Entities;  // NOT .ToList()
}
```

### Nullable Reference Types

```csharp
// DO: Use proper defaults
public string Name { get; set; } = "";

// DON'T: Suppress nullable warnings
public string Name { get; set; } = null!;  // Hides NRE at runtime
```
