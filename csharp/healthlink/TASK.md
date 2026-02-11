# HealthLink - Healthcare Appointment & Patient Management Debugging Challenge

## Overview

HealthLink is a healthcare appointment and patient management platform built with C# 12 and .NET 8. The codebase contains issues across 7 categories that are blocking production deployment. Your task is to identify and fix these bugs to get all tests passing.

## Difficulty

**Senior Engineer Level** - Expected time: 2-4 hours

## Technology Stack

- **Language**: C# 12
- **Framework**: ASP.NET Core 8 (Minimal APIs + Controllers)
- **ORM**: Entity Framework Core 8 + Npgsql
- **Database**: PostgreSQL 16
- **Cache**: Redis 7 (StackExchange.Redis)
- **Patterns**: MediatR, IOptions pattern
- **Testing**: xUnit, FluentAssertions, Moq, Testcontainers

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Run all tests
dotnet test

# Run specific test class
dotnet test --filter "FullyQualifiedName~PatientServiceTests"

# Run tests by namespace
dotnet test --filter "Namespace~HealthLink.Tests.Unit"

# Run with TRX report generation
dotnet test --logger "trx;LogFileName=results.trx"
```

**Important**: Setup bugs (L1-L4) prevent the application from starting correctly. The DI container will fail to resolve services until you fix the circular dependency. Fix these before tackling other categories.

## Bug Categories

### Category L: Setup/DI Configuration

ASP.NET Core dependency injection and configuration issues that block everything else.

| Bug | Description | File |
|-----|-------------|------|
| L1 | Circular dependency between NotificationService and SchedulingService (no `Lazy<T>` available by default in .NET DI) | `src/HealthLink.Api/Services/NotificationService.cs`, `src/HealthLink.Api/Services/SchedulingService.cs` |
| L2 | `AddSingleton<DbContext>` instead of `AddScoped<DbContext>` causes cross-request state leaks | `src/HealthLink.Api/Program.cs` |
| L3 | `IOptions<T>` section name mismatch - `Configure<SmtpSettings>("Email")` but appsettings has `"Smtp"` | `src/HealthLink.Api/Program.cs`, `src/HealthLink.Api/appsettings.json` |
| L4 | Middleware ordering: `UseAuthentication()` called after `MapControllers()` | `src/HealthLink.Api/Program.cs` |

**Tip**: Fix L1 first. The circular dependency prevents all services from resolving, which blocks nearly all tests. Break the cycle by injecting `Func<IServiceProvider>` or restructuring to use an interface.

### Category A: Async/Await

C#-specific async pitfalls: deadlocks, fire-and-forget, ValueTask misuse.

| Bug | Description | File |
|-----|-------------|------|
| A1 | `Task.Result` called on async method in controller - deadlock with SynchronizationContext | `src/HealthLink.Api/Controllers/AppointmentController.cs` |
| A2 | Missing `ConfigureAwait(false)` in library code causes deadlock under ASP.NET sync context | `src/HealthLink.Api/Services/SchedulingService.cs` |
| A3 | `async void` event handler swallows exceptions | `src/HealthLink.Api/Services/NotificationService.cs` |
| A4 | `ValueTask` double-awaited in CacheService | `src/HealthLink.Api/Services/CacheService.cs` |
| A5 | Fire-and-forget `Task` with no error observation in NotificationService | `src/HealthLink.Api/Services/NotificationService.cs` |

**Tip**: For A1, never use `.Result` or `.Wait()` on tasks in ASP.NET Core - use `await` instead. For A3, `async void` methods cannot be caught by callers; change to `async Task` and handle errors. For A4, `ValueTask` can only be awaited once; if you need to await it multiple times, convert to `Task` first with `.AsTask()`.

### Category B: Nullable/Value Types

C# nullable reference types and value type pitfalls.

| Bug | Description | File |
|-----|-------------|------|
| B1 | `null!` suppression hides NullReferenceException - Patient.Name assigned `null!` | `src/HealthLink.Api/Models/Patient.cs` |
| B2 | Struct mutation through interface - modifying boxed `AppointmentSlot` doesn't affect original | `src/HealthLink.Api/Models/AppointmentSlot.cs` |
| B3 | `default(TimeSlot)` creates zero-value struct used as valid data | `src/HealthLink.Api/Models/TimeSlot.cs` |
| B4 | Boxed enum equality - `object.Equals()` on boxed `AppointmentStatus` enums | `src/HealthLink.Api/Services/AppointmentService.cs` |

**Tip**: For B1, `null!` tells the compiler "trust me, this isn't null" - but it is. Remove the suppression and handle nullability properly. For B2, structs are value types; casting to an interface boxes them. Mutations on the boxed copy don't affect the original. For B3, `default` for value types is all-zero, which may be a valid but incorrect value.

### Category C: LINQ/IQueryable

LINQ deferred execution and IQueryable translation pitfalls.

| Bug | Description | File |
|-----|-------------|------|
| C1 | Deferred execution - `IEnumerable` query enumerated multiple times, hitting DB twice | `src/HealthLink.Api/Services/PatientService.cs` |
| C2 | Client-side evaluation - LINQ expression can't translate to SQL, silently pulls all rows | `src/HealthLink.Api/Repositories/AppointmentRepository.cs` |
| C3 | Closure captures loop variable - lambda in LINQ captures `i` by reference | `src/HealthLink.Api/Services/ReportService.cs` |
| C4 | Returning `IEnumerable` instead of `IQueryable` from repository prevents further DB-level filtering | `src/HealthLink.Api/Repositories/PatientRepository.cs` |

**Tip**: For C1, materialize the query with `.ToList()` before iterating multiple times. For C2, EF Core 8 throws by default on client evaluation; this bug has a `EnableDetailedErrors` that hides it. For C3, capture the loop variable in a local before the lambda.

### Category D: IDisposable/Resources

Resource management and disposal pattern issues.

| Bug | Description | File |
|-----|-------------|------|
| D1 | `DbContext` used outside its scope - context disposed but reference held | `src/HealthLink.Api/Services/ReportService.cs` |
| D2 | Event handler leak - `+=` subscription without corresponding `-=` unsubscription | `src/HealthLink.Api/Services/SchedulingService.cs` |
| D3 | `new HttpClient()` per request instead of `IHttpClientFactory` - socket exhaustion | `src/HealthLink.Api/Services/ExternalApiService.cs` |
| D4 | `IAsyncDisposable` not awaited - `await using` required but using regular `using` | `src/HealthLink.Api/Services/ExportService.cs` |

**Tip**: For D1, never store a scoped `DbContext` reference beyond the request scope. For D3, use `IHttpClientFactory.CreateClient()` instead of `new HttpClient()`. For D4, classes implementing `IAsyncDisposable` must use `await using`, not `using`.

### Category E: EF Core

Entity Framework Core-specific issues.

| Bug | Description | File |
|-----|-------------|------|
| E1 | Change tracker returns stale cached entity instead of fresh DB data | `src/HealthLink.Api/Services/PatientService.cs` |
| E2 | `OwnsOne` not configured for value object - Address not persisted | `src/HealthLink.Api/Data/HealthLinkDbContext.cs` |
| E3 | `Include()` causing cartesian explosion with multiple collections - use `AsSplitQuery()` | `src/HealthLink.Api/Repositories/AppointmentRepository.cs` |
| E4 | String columns default to `nvarchar(max)` - no `HasMaxLength()` configured | `src/HealthLink.Api/Data/HealthLinkDbContext.cs` |

**Tip**: For E1, use `AsNoTracking()` for read-only queries or call `context.ChangeTracker.Clear()`. For E2, in EF Core 8, owned types must be explicitly configured with `OwnsOne()` in `OnModelCreating`. For E3, when `Include()`-ing multiple collections, EF Core generates a cartesian product; use `.AsSplitQuery()` to split into multiple SQL queries.

### Category I: Security

Critical security vulnerabilities.

| Bug | Description | File |
|-----|-------------|------|
| I1 | `ExecuteSqlRaw()` with string interpolation - SQL injection | `src/HealthLink.Api/Repositories/PatientRepository.cs` |
| I2 | JWT signing key too short (< 256 bits) - weak cryptographic key | `src/HealthLink.Api/Security/JwtTokenService.cs` |
| I3 | `Path.Combine()` with user input allows path traversal (absolute paths override) | `src/HealthLink.Api/Controllers/DocumentController.cs` |
| I4 | `[AllowAnonymous]` on base controller overrides `[Authorize]` on derived actions | `src/HealthLink.Api/Controllers/PatientController.cs` |

**Tip**: For I1, use `ExecuteSqlInterpolated()` instead of `ExecuteSqlRaw()` with interpolated strings - it parameterizes automatically. For I3, `Path.Combine("/uploads", "../../../etc/passwd")` returns `../../../etc/passwd` on Linux because absolute-looking paths override the base. Validate the final path.

## Test Structure

| Category | Namespace | Tests | Weight |
|----------|-----------|-------|--------|
| Unit | `HealthLink.Tests.Unit.*` | ~55 | 1.0x |
| Integration | `HealthLink.Tests.Integration.*` | ~35 | 1.5x |
| Concurrency | `HealthLink.Tests.Concurrency.*` | ~20 | 2.5x |
| Security | `HealthLink.Tests.Security.*` | ~15 | 2.0x |
| **Total** | | **125+** | |

## Key Files to Investigate

| File | Bug Categories |
|------|---------------|
| `src/HealthLink.Api/Program.cs` | L2, L3, L4 |
| `src/HealthLink.Api/Services/NotificationService.cs` | L1, A3, A5 |
| `src/HealthLink.Api/Services/SchedulingService.cs` | A2, D2 |
| `src/HealthLink.Api/Services/PatientService.cs` | B1, C1, E1 |
| `src/HealthLink.Api/Services/CacheService.cs` | A4 |
| `src/HealthLink.Api/Services/ReportService.cs` | C3, D1 |
| `src/HealthLink.Api/Services/ExternalApiService.cs` | D3 |
| `src/HealthLink.Api/Services/ExportService.cs` | D4 |
| `src/HealthLink.Api/Services/AppointmentService.cs` | B4 |
| `src/HealthLink.Api/Controllers/AppointmentController.cs` | A1 |
| `src/HealthLink.Api/Controllers/PatientController.cs` | I4 |
| `src/HealthLink.Api/Controllers/DocumentController.cs` | I3 |
| `src/HealthLink.Api/Repositories/AppointmentRepository.cs` | C2, E3 |
| `src/HealthLink.Api/Repositories/PatientRepository.cs` | C4, I1 |
| `src/HealthLink.Api/Models/Patient.cs` | B1 |
| `src/HealthLink.Api/Models/AppointmentSlot.cs` | B2 |
| `src/HealthLink.Api/Models/TimeSlot.cs` | B3 |
| `src/HealthLink.Api/Data/HealthLinkDbContext.cs` | E2, E4 |
| `src/HealthLink.Api/Security/JwtTokenService.cs` | I2 |
| `src/HealthLink.Api/appsettings.json` | L3 |

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
- Async fix bonus (+3%) for resolving all async/await issues
- Security fix bonus (+2%) for resolving all security vulnerabilities

### Penalties
- Regression penalty (-15%) for re-breaking previously passing tests

## Debugging Approach

### Phase 1: Fix Setup (L1-L4)

Get the DI container to resolve services. Without this, almost no tests can run.

1. **L1** (Circular DI): Look at `NotificationService` and `SchedulingService`. They inject each other. Break the cycle with `Lazy<T>`, `Func<T>`, or extract a shared interface.
2. **L2** (Singleton DbContext): `AddSingleton<HealthLinkDbContext>()` should be `AddScoped<HealthLinkDbContext>()`. EF Core DbContext is not thread-safe.
3. **L3** (IOptions mismatch): The config section name in `Configure<SmtpSettings>()` doesn't match the appsettings.json key.
4. **L4** (Middleware order): `UseAuthentication()` and `UseAuthorization()` must come before `MapControllers()`.

### Phase 2: Fix Async/Await (A1-A5)

These cause deadlocks and swallowed exceptions.

### Phase 3: Fix LINQ/IQueryable (C1-C4)

Focus on deferred execution and client-side evaluation issues.

### Phase 4: Fix EF Core (E1-E4)

Change tracker, owned types, and query issues.

### Phase 5: Fix IDisposable (D1-D4)

Resource leaks and disposal patterns.

### Phase 6: Fix Nullable/Value Types (B1-B4)

Subtle runtime errors with structs and nullable references.

### Phase 7: Fix Security (I1-I4)

Review every place user input touches SQL, file paths, or auth config.

## Architecture

```
healthlink/
├── src/
│ └── HealthLink.Api/
│ ├── HealthLink.Api.csproj
│ ├── Program.cs # L2, L3, L4
│ ├── Controllers/
│ │ ├── AppointmentController.cs # A1
│ │ ├── PatientController.cs # I4
│ │ └── DocumentController.cs # I3
│ ├── Services/
│ │ ├── PatientService.cs # B1, C1, E1
│ │ ├── AppointmentService.cs # B4
│ │ ├── SchedulingService.cs # A2, D2
│ │ ├── NotificationService.cs # L1, A3, A5
│ │ ├── CacheService.cs # A4
│ │ ├── ReportService.cs # C3, D1
│ │ ├── ExternalApiService.cs # D3
│ │ └── ExportService.cs # D4
│ ├── Repositories/
│ │ ├── AppointmentRepository.cs # C2, E3
│ │ └── PatientRepository.cs # C4, I1
│ ├── Models/
│ │ ├── Patient.cs # B1
│ │ ├── AppointmentSlot.cs # B2
│ │ └── TimeSlot.cs # B3
│ ├── Data/
│ │ └── HealthLinkDbContext.cs # E2, E4
│ ├── Security/
│ │ └── JwtTokenService.cs # I2
│ ├── appsettings.json # L3
│ └── appsettings.Development.json
├── tests/
│ └── HealthLink.Tests/
│ ├── HealthLink.Tests.csproj
│ ├── Unit/
│ ├── Integration/
│ ├── Concurrency/
│ └── Security/
├── HealthLink.sln
├── environment/ # RL environment wrapper
├── Dockerfile
├── docker-compose.yml # PostgreSQL 16, Redis 7
└── docker-compose.test.yml
```

## C#-Specific Patterns to Watch

```csharp
// Task.Result deadlock (BUG A1)
public IActionResult GetAppointment(int id)
{
 var result = _service.GetAsync(id).Result;
 return Ok(result);
}
// Fix: public async Task<IActionResult> GetAppointment(int id)

// Struct mutation through interface (BUG B2)
ISlot slot = new AppointmentSlot { Hour = 9 };
slot.Hour = 10; // Modifies the BOXED COPY, not the original!

// Deferred execution (BUG C1)
IEnumerable<Patient> patients = dbContext.Patients.Where(p => p.Active);
var count = patients.Count(); // DB query 1
var list = patients.ToList(); // DB query 2 - hits DB again!

// Path.Combine injection (BUG I3)
var path = Path.Combine("/uploads", userInput);
// If userInput = "/etc/passwd", result is "/etc/passwd" (absolute overrides!)

// IOptions section mismatch (BUG L3)
builder.Services.Configure<SmtpSettings>(config.GetSection("Email")); // Wrong!
// appsettings.json has "Smtp": { ... }, not "Email": { ... }
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter:

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-startup-failure-incident.md](./scenarios/01-startup-failure-incident.md) | PagerDuty Incident | Critical | Application crash loop, DI container fails |
| [02-security-audit-findings.md](./scenarios/02-security-audit-findings.md) | Security Report | Critical | SQL injection, path traversal, weak JWT |
| [03-appointment-api-timeout.md](./scenarios/03-appointment-api-timeout.md) | Customer Escalation | High | API requests hanging indefinitely |
| [04-socket-exhaustion-alert.md](./scenarios/04-socket-exhaustion-alert.md) | Grafana Alert | Critical | External API failures, socket exhaustion |
| [05-stale-patient-data.md](./scenarios/05-stale-patient-data.md) | Support Ticket | High | Stale cached data, duplicate queries |

Each scenario describes **symptoms only** - the observable behavior and user reports. Use them to practice realistic debugging workflows.

## Hints

1. **Start with L1**: Fix the circular DI dependency first - the service provider cannot build without it
2. **Don't use .Result**: In ASP.NET Core, calling `.Result` or `.Wait()` on async methods causes deadlocks
3. **ValueTask is single-use**: Unlike `Task`, a `ValueTask` can only be awaited once
4. **Structs are copied**: Assignment, passing as parameter, and boxing all create copies
5. **IQueryable is lazy**: Don't enumerate an `IQueryable` multiple times - materialize with `.ToList()` first
6. **Path.Combine is dangerous**: Absolute paths in the second argument override the first argument completely
7. **EF Core change tracker**: Entities loaded by EF Core are cached; use `AsNoTracking()` for read-only queries
8. **IAsyncDisposable needs await**: `await using` is not optional for async disposable resources
9. **ExecuteSqlInterpolated**: Always prefer it over `ExecuteSqlRaw` for parameterized queries

Good luck! Remember: C#'s async/await model is powerful, but understanding SynchronizationContext and value types is essential for debugging.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Patient Medical History Timeline, Notification Channel Consolidation, Appointment Query Optimization, Bulk Patient Operations, Redis Cache Migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Prescription Validation Service, Appointment Reminder System, Lab Results Integration |

These tasks test different software engineering skills while using the same codebase.
