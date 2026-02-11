# EventHorizon - Greenfield Implementation Tasks

## Overview

These three greenfield tasks require implementing brand-new services and modules from scratch for the EventHorizon event ticketing platform. Each task includes detailed interface contracts and architectural requirements that follow established patterns in the codebase.

## Environment

- **Language**: C# 12 / .NET 8
- **Infrastructure**: ASP.NET Core 8, EF Core 8, MassTransit 8, PostgreSQL, Redis, RabbitMQ, Consul
- **Difficulty**: Principal/Staff Engineer
- **Services**: Extend existing 10-service architecture with new specialized services

## Tasks

### Task 1: Waitlist Management Service (Greenfield)

Implement a waitlist management service that allows customers to join waitlists for sold-out events. The service must handle fair queue ordering with priority levels (Standard, Member, VIP, Platinum), automatic ticket offers when availability occurs, time-limited offer expiration, and position tracking. Create `IWaitlistService` and `IWaitlistNotifier` interfaces, supporting types, controllers, and 40+ unit tests. Subscribe to `TicketReleasedEvent` via EventBus and publish `WaitlistOfferCreatedEvent`. Follow established patterns for async/await, dependency injection, and concurrency safety.

**Key Interfaces:**
- `IWaitlistService`: Join/leave waitlist, get position, process availability, claim offers, expire stale offers
- `IWaitlistNotifier`: Notify of offers and position changes

**Models:**
- `WaitlistEntry`, `WaitlistPosition`, `WaitlistOffer`, `OrderHold`
- Enums: `WaitlistPriority`, `WaitlistOfferStatus`

**Architectural Requirements:**
- Create service at port 5010 with standard ASP.NET Core project structure
- Integrate with `IEventBus` for event publishing and subscription
- Use `SemaphoreSlim` for concurrent join handling (no deadlocks)
- Use `decimal` for money (not `float`)
- All async methods with proper `CancellationToken` support
- 40+ unit tests covering concurrency, expiration, priority ordering

### Task 2: Ticket Transfer System (Greenfield)

Implement a peer-to-peer ticket transfer system allowing customers to transfer purchased tickets to other users. The system must track complete ownership chains, validate transfer eligibility, calculate transfer fees per event policy, handle pending transfer expiration, and process both acceptance and decline scenarios. Create `ITransferService` and `ITransferValidator` interfaces, supporting types, controllers, and 45+ unit tests. Use secure random tokens for acceptance links, publish `TicketTransferredEvent`, and integrate with notification services.

**Key Interfaces:**
- `ITransferService`: Initiate/accept/decline/cancel transfers, get ownership history, calculate fees, get pending transfers
- `ITransferValidator`: Validate transfer eligibility, check transfer limit

**Models:**
- `TransferRequest`, `TransferResult`, `OwnershipRecord`, `TransferValidation`, `TransferPolicy`
- Enums: `TransferStatus`

**Architectural Requirements:**
- Create service at port 5011 with standard ASP.NET Core project structure
- Validate ticket ownership before transfer initiation
- Generate cryptographically secure acceptance tokens
- Maintain complete ownership provenance chain
- Handle transfer chain limits (max 3 transfers per ticket)
- Rate limit transfer requests per customer
- 45+ unit tests covering transfer validation, fees, race conditions, expiration

### Task 3: Venue Capacity Optimizer (Greenfield)

Implement a venue capacity optimization service that dynamically adjusts section availability, pricing, and seat configurations based on demand patterns and accessibility requirements. The service must analyze sales velocity, calculate dynamic pricing with floor/ceiling bounds, reserve ADA-compliant accessible seating, stream real-time capacity updates, and recommend/apply capacity adjustments. Create `ICapacityOptimizerService` and `ISectionManager` interfaces, supporting types, controllers, and 50+ unit tests. Subscribe to demand signals and publish section/price change events.

**Key Interfaces:**
- `ICapacityOptimizerService`: Analyze capacity, apply adjustments, get demand metrics, calculate dynamic pricing, reserve accessible seats, stream capacity updates
- `ISectionManager`: Open/close sections, reconfigure seating

**Models:**
- `CapacityAnalysis`, `SectionAnalysis`, `CapacityAdjustment`, `AdjustmentResult`, `DemandMetrics`
- `PricingRecommendation`, `AccessibleAllocation`, `CapacitySnapshot`
- `SectionConfiguration`, `SectionClosure`, `SeatingLayout`, `ReconfigurationResult`
- Enums: `AdjustmentType`, `ExistingReservationStrategy`, `SeatingType`

**Architectural Requirements:**
- Create service at port 5012 with standard ASP.NET Core project structure
- Use `IAsyncEnumerable<T>` for real-time capacity streaming
- Use `decimal` for all pricing (not `float`)
- Cache demand metrics with Redis TTL patterns
- Use `SemaphoreSlim` for rate limiting concurrent adjustments
- Implement circuit breaker for external service resilience
- Use `Channel<T>` for backpressure in streaming
- 50+ unit tests covering thread safety, ADA compliance, pricing boundaries, streaming

## General Requirements

### Code Quality Standards

1. **Follow existing patterns:**
   - Interface-based dependency injection
   - Async/await throughout (never sync-over-async)
   - Nullable reference types enabled (`<Nullable>enable</Nullable>`)
   - XML documentation on all public members

2. **Avoid known bug patterns:**
   - No `Task.Result` or `.Wait()` calls
   - No `float` for monetary values (use `decimal`)
   - No `async void` methods (except event handlers)
   - Proper `CancellationToken` propagation in all async methods
   - No struct copy bugs (use `readonly record struct` where appropriate)
   - Exhaustive enum switch coverage with `_` catch-all

3. **Testing standards:**
   - Use xUnit with FluentAssertions
   - Mock dependencies with Moq
   - Test success and failure paths
   - Test boundary conditions and edge cases
   - Test concurrent/parallel scenarios

### Project File Templates

**Service Project:**
```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>EventHorizon.[ServiceName]</RootNamespace>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="..\Shared\Shared.csproj" />
  </ItemGroup>
</Project>
```

**Test Project:**
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.9.0" />
    <PackageReference Include="xunit" Version="2.7.0" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.7" />
    <PackageReference Include="FluentAssertions" Version="6.12.0" />
    <PackageReference Include="Moq" Version="4.20.70" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="..\..\src\[ServiceName]\[ServiceName].csproj" />
  </ItemGroup>
</Project>
```

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run all tests
dotnet test

# Or run in Docker
docker compose -f docker-compose.test.yml up --build

# Run specific service tests
dotnet test tests/Waitlist.Tests/
dotnet test tests/Transfers.Tests/
dotnet test tests/Optimizer.Tests/
```

## Success Criteria

- All interface contracts implemented as specified
- Required models and enums defined
- 40+ (Waitlist), 45+ (Transfers), 50+ (Optimizer) unit tests passing
- Proper integration with `IEventBus` for event publishing
- Proper integration with existing services (Tickets, Notifications, Analytics)
- No setup/build errors
- All async patterns follow best practices (no sync-over-async)
- All monetary calculations use `decimal` type
- Thread safety verified through concurrent tests
- All existing tests continue to pass
