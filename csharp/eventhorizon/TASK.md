# EventHorizon - Distributed Event Ticketing Platform

## Task Description

You are debugging a distributed event ticketing platform built with C# 12 and .NET 8, organized as 10 ASP.NET Core microservices. The platform handles event creation, ticket inventory, order processing, payments, venue management, real-time notifications, analytics, and search for live events and concerts.

The codebase contains issues across 10 microservices and a shared library that need to be identified and fixed. All 510+ tests must pass before the task is complete.

**Difficulty Level**: Principal/Staff Engineer (8-16 hours expected)

## Getting Started

```bash
# Start infrastructure services
docker compose up -d

# Run all tests in Docker
docker compose -f docker-compose.test.yml up --build

# Or run tests locally
dotnet test

# Run tests for a specific service
dotnet test tests/Orders.Tests/
```

## Architecture

EventHorizon is a multi-project .NET solution with 10 ASP.NET Core microservices and a shared library:

```
eventhorizon/
├── src/
│ ├── Shared/ # Shared library (config, events, security, models)
│ ├── Gateway/ # API Gateway - Port 5000
│ ├── Auth/ # Authentication & JWT - Port 5001
│ ├── Events/ # Event CRUD & Management - Port 5002
│ ├── Tickets/ # Ticket Inventory & Seat Maps - Port 5003
│ ├── Orders/ # Order Lifecycle & Sagas - Port 5004
│ ├── Payments/ # Payment Processing & Refunds - Port 5005
│ ├── Venues/ # Venue Management & Layouts - Port 5006
│ ├── Notifications/ # SignalR Real-Time Notifications - Port 5007
│ ├── Analytics/ # Sales Analytics & Reporting - Port 5008
│ └── Search/ # Full-Text Search & Indexing - Port 5009
├── tests/
│ ├── Shared.Tests/
│ ├── Gateway.Tests/
│ ├── Auth.Tests/
│ ├── Events.Tests/
│ ├── Tickets.Tests/
│ ├── Orders.Tests/
│ ├── Payments.Tests/
│ ├── Venues.Tests/
│ ├── Notifications.Tests/
│ ├── Analytics.Tests/
│ └── Search.Tests/
├── environment/ # RL environment wrapper
├── EventHorizon.sln
└── docker-compose.yml
```

### Services

| Service | Port | Purpose |
| Gateway | 5000 | REST API entry point, rate limiting, request routing |
| Auth | 5001 | JWT authentication, API keys, RBAC |
| Events | 5002 | Event CRUD, scheduling, capacity management |
| Tickets | 5003 | Ticket inventory, seat maps, availability |
| Orders | 5004 | Order lifecycle, saga orchestration, checkout |
| Payments | 5005 | Payment processing, refunds, revenue tracking |
| Venues | 5006 | Venue management, floor plans, sections |
| Notifications | 5007 | SignalR real-time push, email, SMS |
| Analytics | 5008 | Sales reports, demand forecasting, KPIs |
| Search | 5009 | Full-text search, faceted filtering, suggestions |

### Infrastructure

| Component | Purpose |
|-----------|---------|
| RabbitMQ 3.13 | Message bus, inter-service events via MassTransit |
| PostgreSQL 16 | Persistent storage (events_db, orders_db, payments_db) |
| Redis 7 | Distributed caching, rate limiting, locks |
| Consul 1.17 | Service discovery, distributed configuration |

## Technology Stack

- **Language**: C# 12
- **Framework**: ASP.NET Core 8 (Minimal APIs + Controllers)
- **ORM**: Entity Framework Core 8 + Npgsql
- **Messaging**: MassTransit 8 + RabbitMQ
- **Real-Time**: SignalR
- **RPC**: gRPC
- **Resilience**: Polly v8
- **Patterns**: MediatR, IOptions, Outbox
- **Testing**: xUnit, FluentAssertions, Moq

## Key Challenges

1. **Setup Hell**: Services will not start initially. You must fix circular dependencies (L1), DbContext registration (L2), and config loading (L3) before any tests can run.

2. **Multi-Service Debugging**: Bugs span multiple services. A fix in the shared library may unblock tests in several downstream services.

3. **Cascading Failures**: Some bugs depend on others being fixed first. Some bugs have explicit prerequisites, with dependency chains up to depth 5.

4. **C#-Specific Pitfalls**: Many bugs exploit C#-specific traps:
 - `Task.Result` deadlocks with SynchronizationContext
 - `ValueTask` can only be awaited once
 - Structs are value types - boxing creates copies
 - `Path.Combine` with absolute paths overrides the base
 - `ExecuteSqlRaw` with interpolation is SQL injection
 - `[AllowAnonymous]` on class overrides `[Authorize]` on methods
 - Record equality doesn't compare collection contents
 - `IAsyncDisposable` requires `await using`

## Scoring

Principal-level very sparse reward function:

| Bug Fix Rate | Reward |
|-------------|--------|
| < 10% | 0.00 |
| 10-24% | 0.00-0.05 |
| 25-39% | 0.05-0.12 |
| 40-54% | 0.12-0.22 |
| 55-69% | 0.22-0.38 |
| 70-84% | 0.38-0.55 |
| 85-94% | 0.55-0.78 |
| 95-100% | 0.78-1.00 |

### Bonuses
- Category completion: +1% per complete category
- Service completion: +1% per fully-fixed service

### Penalties
- Regression: -3% per previously-passing test that now fails

## Debugging Approach

### Phase 1: Fix Setup (L1-L6)
Get all services to start. Fix circular DI, DbContext registration, config loading.

### Phase 2: Fix Async/Await (A1-A8)
Resolve deadlocks and swallowed exceptions.

### Phase 3: Fix EF Core (E1-E7)
Change tracker, owned types, query issues.

### Phase 4: Fix Security (I1-I7)
SQL injection, path traversal, auth issues.

### Phase 5: Fix Remaining Categories
Work through LINQ, IDisposable, gRPC/SignalR, MassTransit, distributed state, serialization, and modern C# bugs.

## C#-Specific Patterns to Watch

```csharp
// Task.Result deadlock (BUG A1)
public IActionResult Get(int id)
{
 var result = _service.GetAsync(id).Result; // DEADLOCK!
 return Ok(result);
}

// ValueTask double-await (BUG A4)
var vt = cache.GetAsync("key");
var first = await vt; // OK
var second = await vt; // UNDEFINED BEHAVIOR!

// Record collection equality (BUG K1)
record Order(string Id, List<string> Items);
var a = new Order("1", new() { "A" });
var b = new Order("1", new() { "A" });
a == b; // FALSE! List reference equality, not content

// Path.Combine injection (BUG I2)
Path.Combine("/uploads", "/etc/passwd"); // Returns "/etc/passwd"!

// ExecuteSqlRaw injection (BUG I1)
db.Database.ExecuteSqlRawAsync($"UPDATE x SET y = '{input}'"); // SQL INJECTION!
// Fix: db.Database.ExecuteSqlInterpolatedAsync($"UPDATE x SET y = {input}");

// Primary constructor capture (BUG K6)
class Service(ILogger logger) // logger is captured as a field
{
 private readonly ILogger _logger = logger; // BOTH fields exist!
}
```

## Debugging Scenarios

For a more realistic debugging experience, check out the [scenarios/](./scenarios/) directory. These contain production-style incidents, security reports, and QA test failures that describe symptoms without revealing fixes:

| Scenario | Type | Description |
| [Double Charge Incident](./scenarios/01-double-charge-incident.md) | PagerDuty | Flash sale causes duplicate payment charges |
| [Security Assessment](./scenarios/02-security-assessment-report.md) | Audit Report | JWT weakness, SQL injection, auth bypass |
| [Memory Leak](./scenarios/03-notification-memory-leak.md) | Grafana Alert | Notification service memory growth |
| [Order Deadlock](./scenarios/04-order-saga-deadlock.md) | Escalation | Orders stuck in processing, thread deadlocks |
| [Data Inconsistency](./scenarios/05-data-inconsistency-report.md) | QA Report | Serialization and value type issues |

These scenarios train realistic debugging skills - investigating from symptoms rather than knowing where bugs are.

## Verification

```bash
# Run all tests
dotnet test

# Run specific service tests
dotnet test tests/Orders.Tests/

# Run by namespace
dotnet test --filter "Namespace~EventHorizon.Orders.Tests"

# Run specific test
dotnet test --filter "FullyQualifiedName~test_no_task_result_deadlock"

# Generate TRX report
dotnet test --logger "trx;LogFileName=results.trx"
```

Good luck! This is a Principal-level challenge requiring deep understanding of C# async patterns, .NET DI, EF Core, and distributed systems.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Dynamic Pricing, Order Saga, Search Caching, Bulk Ops, Event Sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Waitlist Management, Ticket Transfer, Venue Optimizer |

These tasks test different software engineering skills while using the same codebase.
