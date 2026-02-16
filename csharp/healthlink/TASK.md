# HealthLink - Healthcare Appointment & Patient Management Debugging Challenge

## Overview

HealthLink is a healthcare appointment and patient management platform built with C# 12 and .NET 8. The codebase contains bugs across 7 categories that are blocking production deployment. Your task is to identify and fix these bugs to get all tests passing.

## Difficulty

**Senior Engineer Level** - Expected time: 2-4 hours

## Technology Stack

- **Language**: C# 12
- **Framework**: ASP.NET Core 8 (Minimal APIs + Controllers)
- **ORM**: Entity Framework Core 8 + Npgsql
- **Database**: PostgreSQL 16
- **Cache**: Redis 7 (StackExchange.Redis)
- **Patterns**: MediatR, IOptions pattern
- **Testing**: xUnit, FluentAssertions, Moq

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
```

**Important**: Some bugs prevent the DI container from resolving services. Fix service registration and dependency issues before tackling other categories.

## Bug Categories

### Category L: Setup/DI Configuration (4 bugs)

ASP.NET Core dependency injection and configuration issues that block everything else. Includes circular dependencies, incorrect service lifetimes, configuration binding errors, and middleware ordering problems.

### Category A: Async/Await (5 bugs)

C#-specific async pitfalls including synchronous blocking on async methods, missing `ConfigureAwait`, improper async method signatures, `ValueTask` misuse, and unobserved exceptions from fire-and-forget tasks.

### Category B: Nullable/Value Types (4 bugs)

C# nullable reference types and value type pitfalls including null suppression operators hiding runtime errors, struct boxing and mutation through interfaces, default value type behavior, and boxed equality comparison issues.

### Category C: LINQ/IQueryable (4 bugs)

LINQ deferred execution and IQueryable translation pitfalls including multiple enumeration, client-side evaluation of non-translatable expressions, closure variable capture in loops, and repository method return type issues.

### Category D: IDisposable/Resources (4 bugs)

Resource management and disposal pattern issues including scoped resource leaks, event handler subscription leaks, HTTP client connection management, and async disposable patterns.

### Category E: EF Core (4 bugs)

Entity Framework Core-specific issues including change tracker caching, value object persistence configuration, query performance problems with multiple includes, and string column sizing.

### Category I: Security (4 bugs)

Critical security vulnerabilities including SQL injection through raw query construction, weak cryptographic keys, path traversal via file path manipulation, and authorization attribute precedence issues.

## Test Structure

| Category | Namespace | Tests |
|----------|-----------|-------|
| Unit | `HealthLink.Tests.Unit.*` | ~73 |
| Integration | `HealthLink.Tests.Integration.*` | ~20 |
| Concurrency | `HealthLink.Tests.Concurrency.*` | ~15 |
| Security | `HealthLink.Tests.Security.*` | ~20 |
| **Total** | | **~128** |

## Key Files

| Directory | Contents |
|-----------|----------|
| `src/HealthLink.Api/Program.cs` | Application startup, DI registration, middleware pipeline |
| `src/HealthLink.Api/Controllers/` | API controllers |
| `src/HealthLink.Api/Services/` | Business logic services |
| `src/HealthLink.Api/Repositories/` | Data access layer |
| `src/HealthLink.Api/Models/` | Domain models and value types |
| `src/HealthLink.Api/Data/` | EF Core DbContext and configuration |
| `src/HealthLink.Api/Security/` | Authentication and JWT services |
| `src/HealthLink.Api/appsettings.json` | Application configuration |

## Scoring

Your score is based on the percentage of tests passing:

| Pass Rate | Reward |
|-----------|--------|
| < 50% | 0.00 |
| >= 50% | 0.15 |
| >= 75% | 0.35 |
| >= 90% | 0.65 |
| 100% | 1.00 |

## Debugging Approach

1. **Start with DI/Setup**: Get the dependency injection container to resolve all services first. Without this, most tests can't run.
2. **Fix Async Issues**: Address deadlocks and exception handling problems.
3. **Fix Data Access**: Address LINQ, EF Core, and repository issues.
4. **Fix Resource Management**: Address disposal and leak issues.
5. **Fix Type System Issues**: Address nullable and value type problems.
6. **Fix Security**: Review SQL queries, file paths, crypto config, and auth setup.

## Architecture

```
healthlink/
├── src/
│   └── HealthLink.Api/
│       ├── HealthLink.Api.csproj
│       ├── Program.cs
│       ├── Controllers/
│       ├── Services/
│       ├── Repositories/
│       ├── Models/
│       ├── Data/
│       ├── Security/
│       ├── appsettings.json
│       └── appsettings.Development.json
├── tests/
│   └── HealthLink.Tests/
│       ├── Unit/
│       ├── Integration/
│       ├── Concurrency/
│       └── Security/
├── HealthLink.sln
├── docker-compose.yml
└── docker-compose.test.yml
```

Good luck! Remember: run `dotnet test` frequently to track your progress and pay attention to error messages and stack traces.
