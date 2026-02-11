# EventHorizon - Greenfield Implementation Tasks

These tasks require implementing NEW modules from scratch for the EventHorizon event ticketing platform. Each task must follow the existing architectural patterns established in the codebase.

**Test Command**: `dotnet test`

---

## Task 1: Waitlist Management Service

### Overview

Implement a waitlist management service that allows customers to join waitlists for sold-out events and receive notifications when tickets become available. The service must handle fair queue ordering, automatic ticket offers, and expiration of unclaimed offers.

### Interface Contract

Create the following in `src/Waitlist/Services/WaitlistService.cs`:

```csharp
using EventHorizon.Shared.Models;

namespace EventHorizon.Waitlist.Services;

/// <summary>
/// Manages event waitlists for sold-out events.
/// </summary>
public interface IWaitlistService
{
    /// <summary>
    /// Adds a customer to the waitlist for a specific event.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="customerId">The customer identifier.</param>
    /// <param name="quantity">Number of tickets requested (1-10).</param>
    /// <param name="priority">Optional priority level for VIP customers.</param>
    /// <returns>The waitlist entry with position information.</returns>
    /// <exception cref="InvalidOperationException">Thrown when event is not sold out or customer already on waitlist.</exception>
    Task<WaitlistEntry> JoinWaitlistAsync(int eventId, string customerId, int quantity, WaitlistPriority priority = WaitlistPriority.Standard);

    /// <summary>
    /// Removes a customer from an event waitlist.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="customerId">The customer identifier.</param>
    /// <returns>True if removed, false if not found.</returns>
    Task<bool> LeaveWaitlistAsync(int eventId, string customerId);

    /// <summary>
    /// Gets the current position in the waitlist for a customer.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="customerId">The customer identifier.</param>
    /// <returns>Position info or null if not on waitlist.</returns>
    Task<WaitlistPosition?> GetPositionAsync(int eventId, string customerId);

    /// <summary>
    /// Processes available tickets and creates offers for waitlisted customers.
    /// Called when tickets are released (cancellations, refunds, new inventory).
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="availableQuantity">Number of tickets now available.</param>
    /// <returns>List of offers created for waitlisted customers.</returns>
    Task<List<WaitlistOffer>> ProcessAvailabilityAsync(int eventId, int availableQuantity);

    /// <summary>
    /// Claims a waitlist offer and converts it to an order hold.
    /// </summary>
    /// <param name="offerId">The offer identifier.</param>
    /// <param name="customerId">The customer claiming the offer.</param>
    /// <returns>Order hold information for checkout.</returns>
    /// <exception cref="InvalidOperationException">Thrown when offer expired or already claimed.</exception>
    Task<OrderHold> ClaimOfferAsync(string offerId, string customerId);

    /// <summary>
    /// Expires unclaimed offers and moves tickets to next in queue.
    /// </summary>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Number of offers expired.</returns>
    Task<int> ExpireStaleOffersAsync(CancellationToken ct = default);
}

/// <summary>
/// Manages waitlist notifications via the event bus.
/// </summary>
public interface IWaitlistNotifier
{
    /// <summary>
    /// Sends a notification when a customer receives a waitlist offer.
    /// </summary>
    Task NotifyOfferAvailableAsync(WaitlistOffer offer);

    /// <summary>
    /// Sends a notification when a waitlist offer is about to expire.
    /// </summary>
    Task NotifyOfferExpiringAsync(WaitlistOffer offer, TimeSpan timeRemaining);

    /// <summary>
    /// Sends a notification when a customer's position in the queue changes.
    /// </summary>
    Task NotifyPositionChangedAsync(int eventId, string customerId, int oldPosition, int newPosition);
}
```

### Required Classes/Records

Create in `src/Waitlist/Models/`:

```csharp
namespace EventHorizon.Waitlist.Models;

public enum WaitlistPriority
{
    Standard = 0,
    Member = 1,
    VIP = 2,
    Platinum = 3
}

public enum WaitlistOfferStatus
{
    Pending = 0,
    Claimed = 1,
    Expired = 2,
    Declined = 3
}

public record WaitlistEntry(
    string EntryId,
    int EventId,
    string CustomerId,
    int Quantity,
    WaitlistPriority Priority,
    DateTime JoinedAt,
    int Position);

public record WaitlistPosition(
    int Position,
    int TotalInQueue,
    int EstimatedWaitMinutes,
    DateTime JoinedAt);

public record WaitlistOffer(
    string OfferId,
    int EventId,
    string CustomerId,
    int TicketQuantity,
    Money UnitPrice,
    DateTime CreatedAt,
    DateTime ExpiresAt,
    WaitlistOfferStatus Status);

public record OrderHold(
    string HoldId,
    int EventId,
    string CustomerId,
    List<string> TicketIds,
    Money TotalPrice,
    DateTime HoldExpiresAt);
```

### Architectural Requirements

1. **Project Structure**:
   - Create `src/Waitlist/Waitlist.csproj` referencing `Shared.csproj`
   - Create `src/Waitlist/Controllers/WaitlistController.cs` with REST endpoints
   - Create `src/Waitlist/Program.cs` following the pattern in other services (port 5010)
   - Create `tests/Waitlist.Tests/Waitlist.Tests.csproj` and `WaitlistTests.cs`

2. **Integration Points**:
   - Subscribe to `TicketReleasedEvent` from the Events service via `IEventBus`
   - Publish `WaitlistOfferCreatedEvent` for the Notifications service
   - Use `ITicketInventoryService` pattern for ticket reservation

3. **Patterns to Follow**:
   - Use `async/await` properly (avoid `Task.Result` - see BUG A1 pattern)
   - Use `CancellationToken` in all async streams (see BUG A5 pattern)
   - Implement `IAsyncDisposable` for any resources (see BUG D4 pattern)
   - Use `decimal` for money calculations, not `float` (see BUG B2 pattern)

4. **Concurrency Requirements**:
   - Use `SemaphoreSlim` with consistent lock ordering (avoid BUG G4 deadlock pattern)
   - Ensure idempotent offer claiming (avoid BUG G3 double-charge pattern)

### Acceptance Criteria

- [ ] 40+ unit tests covering all interface methods
- [ ] Tests for concurrent waitlist joins (race conditions)
- [ ] Tests for offer expiration edge cases
- [ ] Tests for priority queue ordering (VIP before Standard)
- [ ] Integration with existing `IEventBus` for event publishing
- [ ] No `Task.Result` or `Task.Wait()` calls (async all the way)
- [ ] All nullable reference types properly handled
- [ ] Controller returns proper HTTP status codes (201 Created, 404 Not Found, 409 Conflict)

---

## Task 2: Ticket Transfer System

### Overview

Implement a ticket transfer system that allows customers to transfer purchased tickets to other users. The system must handle transfer requests, recipient acceptance, ownership chain tracking, and transfer fee calculations.

### Interface Contract

Create the following in `src/Transfers/Services/TransferService.cs`:

```csharp
using EventHorizon.Shared.Models;

namespace EventHorizon.Transfers.Services;

/// <summary>
/// Manages peer-to-peer ticket transfers between customers.
/// </summary>
public interface ITransferService
{
    /// <summary>
    /// Initiates a ticket transfer from one customer to another.
    /// </summary>
    /// <param name="ticketId">The ticket to transfer.</param>
    /// <param name="fromCustomerId">Current ticket owner.</param>
    /// <param name="toEmail">Recipient's email address.</param>
    /// <param name="personalMessage">Optional message to recipient.</param>
    /// <returns>Transfer request with acceptance link.</returns>
    /// <exception cref="InvalidOperationException">Thrown when ticket is not transferable or already pending transfer.</exception>
    Task<TransferRequest> InitiateTransferAsync(
        string ticketId,
        string fromCustomerId,
        string toEmail,
        string? personalMessage = null);

    /// <summary>
    /// Accepts a pending transfer, completing the ownership change.
    /// </summary>
    /// <param name="transferId">The transfer request identifier.</param>
    /// <param name="recipientCustomerId">The accepting customer's ID.</param>
    /// <returns>Updated ticket with new ownership.</returns>
    /// <exception cref="InvalidOperationException">Thrown when transfer expired or already processed.</exception>
    Task<TransferResult> AcceptTransferAsync(string transferId, string recipientCustomerId);

    /// <summary>
    /// Declines a pending transfer, returning ticket to original owner.
    /// </summary>
    /// <param name="transferId">The transfer request identifier.</param>
    /// <param name="reason">Optional decline reason.</param>
    /// <returns>True if declined successfully.</returns>
    Task<bool> DeclineTransferAsync(string transferId, string? reason = null);

    /// <summary>
    /// Cancels a pending transfer initiated by the sender.
    /// </summary>
    /// <param name="transferId">The transfer request identifier.</param>
    /// <param name="requesterId">The original sender's customer ID.</param>
    /// <returns>True if cancelled successfully.</returns>
    Task<bool> CancelTransferAsync(string transferId, string requesterId);

    /// <summary>
    /// Gets the complete ownership history for a ticket.
    /// </summary>
    /// <param name="ticketId">The ticket identifier.</param>
    /// <returns>Chronological list of ownership records.</returns>
    Task<List<OwnershipRecord>> GetOwnershipHistoryAsync(string ticketId);

    /// <summary>
    /// Calculates the transfer fee for a ticket based on event policies.
    /// </summary>
    /// <param name="ticketId">The ticket identifier.</param>
    /// <returns>Transfer fee amount (may be zero for some events).</returns>
    Task<Money> CalculateTransferFeeAsync(string ticketId);

    /// <summary>
    /// Gets all pending transfers for a customer (both sent and received).
    /// </summary>
    /// <param name="customerId">The customer identifier.</param>
    /// <returns>List of pending transfer requests.</returns>
    Task<List<TransferRequest>> GetPendingTransfersAsync(string customerId);
}

/// <summary>
/// Validates transfer eligibility based on event and ticket rules.
/// </summary>
public interface ITransferValidator
{
    /// <summary>
    /// Checks if a ticket can be transferred.
    /// </summary>
    /// <param name="ticketId">The ticket to validate.</param>
    /// <param name="requesterId">The customer requesting transfer.</param>
    /// <returns>Validation result with any blocking reasons.</returns>
    Task<TransferValidation> ValidateTransferAsync(string ticketId, string requesterId);

    /// <summary>
    /// Checks if transfer limit has been reached for an event.
    /// Some events limit how many times a ticket can be transferred.
    /// </summary>
    /// <param name="ticketId">The ticket identifier.</param>
    /// <returns>True if more transfers are allowed.</returns>
    Task<bool> CanTransferAgainAsync(string ticketId);
}
```

### Required Classes/Records

Create in `src/Transfers/Models/`:

```csharp
namespace EventHorizon.Transfers.Models;

public enum TransferStatus
{
    Pending = 0,
    Accepted = 1,
    Declined = 2,
    Cancelled = 3,
    Expired = 4
}

public record TransferRequest(
    string TransferId,
    string TicketId,
    string FromCustomerId,
    string ToEmail,
    string? ToCustomerId,
    string? PersonalMessage,
    Money TransferFee,
    TransferStatus Status,
    DateTime CreatedAt,
    DateTime ExpiresAt,
    string AcceptanceToken);

public record TransferResult(
    string TransferId,
    string TicketId,
    string NewOwnerId,
    string PreviousOwnerId,
    DateTime TransferredAt,
    Money FeePaid,
    string NewTicketBarcode);

public record OwnershipRecord(
    string TicketId,
    string CustomerId,
    string CustomerEmail,
    DateTime AcquiredAt,
    string AcquisitionType,  // "Purchase", "Transfer", "Gift"
    string? PreviousOwnerId);

public record TransferValidation(
    bool IsValid,
    List<string> BlockingReasons,
    int TransfersRemaining,
    Money EstimatedFee);

public record TransferPolicy(
    int EventId,
    bool TransfersAllowed,
    int MaxTransfersPerTicket,
    decimal TransferFeePercent,
    Money MinimumTransferFee,
    TimeSpan TransferCutoffBeforeEvent);
```

### Architectural Requirements

1. **Project Structure**:
   - Create `src/Transfers/Transfers.csproj` referencing `Shared.csproj`
   - Create `src/Transfers/Controllers/TransferController.cs` with REST endpoints
   - Create `src/Transfers/Program.cs` (port 5011)
   - Create `tests/Transfers.Tests/Transfers.Tests.csproj` and `TransferTests.cs`

2. **Integration Points**:
   - Query `ITicketInventoryService` to verify ticket ownership
   - Publish `TicketTransferredEvent` to `IEventBus`
   - Integrate with `INotificationService` for email notifications
   - Use `IPaymentService` pattern for transfer fee processing

3. **Patterns to Follow**:
   - Use `Expression<Func<T, bool>>` for queryable filters (avoid BUG C5 pattern)
   - Handle nullable reference types properly (avoid BUG B1 pattern)
   - Use proper enum switch coverage (avoid BUG K2 pattern)
   - Implement optimistic concurrency for ownership changes (avoid BUG E5 pattern)

4. **Security Requirements**:
   - Generate cryptographically secure acceptance tokens
   - Validate ticket ownership before allowing transfer initiation
   - Rate limit transfer requests per customer

### Acceptance Criteria

- [ ] 45+ unit tests covering all interface methods
- [ ] Tests for transfer chain limits (max 3 transfers per ticket)
- [ ] Tests for transfer fee calculations with different policies
- [ ] Tests for expired transfer cleanup
- [ ] Tests for concurrent accept/decline race conditions
- [ ] Ownership history includes complete provenance chain
- [ ] Transfer tokens use secure random generation
- [ ] Proper HTTP status codes (202 Accepted for async operations)
- [ ] All `TransferStatus` values handled in switch expressions with exhaustive coverage

---

## Task 3: Venue Capacity Optimizer

### Overview

Implement a venue capacity optimization service that dynamically adjusts section availability, pricing, and seat configurations based on demand patterns, accessibility requirements, and event-specific needs. The optimizer uses real-time sales data to maximize revenue while ensuring fair access.

### Interface Contract

Create the following in `src/Optimizer/Services/CapacityOptimizerService.cs`:

```csharp
using EventHorizon.Shared.Models;

namespace EventHorizon.Optimizer.Services;

/// <summary>
/// Optimizes venue capacity allocation and pricing based on demand.
/// </summary>
public interface ICapacityOptimizerService
{
    /// <summary>
    /// Analyzes current sales velocity and recommends section adjustments.
    /// </summary>
    /// <param name="eventId">The event to analyze.</param>
    /// <returns>Optimization recommendations ranked by impact.</returns>
    Task<CapacityAnalysis> AnalyzeCapacityAsync(int eventId);

    /// <summary>
    /// Applies a capacity adjustment (open/close sections, adjust pricing).
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="adjustment">The adjustment to apply.</param>
    /// <returns>Result of the adjustment with affected ticket count.</returns>
    Task<AdjustmentResult> ApplyAdjustmentAsync(int eventId, CapacityAdjustment adjustment);

    /// <summary>
    /// Gets real-time demand metrics for an event.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <returns>Current demand indicators and trends.</returns>
    Task<DemandMetrics> GetDemandMetricsAsync(int eventId);

    /// <summary>
    /// Calculates optimal dynamic pricing for a section based on demand.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="sectionId">The section identifier.</param>
    /// <returns>Recommended price with confidence interval.</returns>
    Task<PricingRecommendation> CalculateDynamicPriceAsync(int eventId, string sectionId);

    /// <summary>
    /// Reserves accessible seating allocation according to ADA requirements.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="accessibleSeatsRequired">Number of accessible seats needed.</param>
    /// <returns>Reserved accessible seat allocations.</returns>
    Task<AccessibleAllocation> ReserveAccessibleSeatsAsync(int eventId, int accessibleSeatsRequired);

    /// <summary>
    /// Streams capacity updates in real-time for monitoring dashboards.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="ct">Cancellation token to stop the stream.</param>
    /// <returns>Async stream of capacity snapshots.</returns>
    IAsyncEnumerable<CapacitySnapshot> StreamCapacityUpdatesAsync(int eventId, CancellationToken ct);
}

/// <summary>
/// Manages section-level seat configurations.
/// </summary>
public interface ISectionManager
{
    /// <summary>
    /// Opens a section for sales with specified configuration.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="sectionConfig">Section configuration to apply.</param>
    /// <returns>Number of tickets made available.</returns>
    Task<int> OpenSectionAsync(int eventId, SectionConfiguration sectionConfig);

    /// <summary>
    /// Closes a section and handles existing reservations.
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="sectionId">The section to close.</param>
    /// <param name="handleExisting">Strategy for existing reservations.</param>
    /// <returns>Closure result with affected reservations.</returns>
    Task<SectionClosure> CloseSectionAsync(int eventId, string sectionId, ExistingReservationStrategy handleExisting);

    /// <summary>
    /// Reconfigures seating layout (e.g., convert GA to reserved).
    /// </summary>
    /// <param name="eventId">The event identifier.</param>
    /// <param name="sectionId">The section to reconfigure.</param>
    /// <param name="newLayout">New seating layout configuration.</param>
    /// <returns>Reconfiguration result.</returns>
    Task<ReconfigurationResult> ReconfigureSectionAsync(int eventId, string sectionId, SeatingLayout newLayout);
}
```

### Required Classes/Records

Create in `src/Optimizer/Models/`:

```csharp
namespace EventHorizon.Optimizer.Models;

public enum AdjustmentType
{
    OpenSection = 0,
    CloseSection = 1,
    PriceIncrease = 2,
    PriceDecrease = 3,
    ReleasePremium = 4,
    HoldInventory = 5
}

public enum ExistingReservationStrategy
{
    MoveToEquivalent = 0,
    Refund = 1,
    UpgradeToNext = 2,
    BlockUntilEmpty = 3
}

public enum SeatingType
{
    Reserved = 0,
    GeneralAdmission = 1,
    VIPBox = 2,
    Accessible = 3,
    Standing = 4
}

public record CapacityAnalysis(
    int EventId,
    int TotalCapacity,
    int SoldCount,
    int HeldCount,
    int AvailableCount,
    decimal SellThroughRate,
    List<SectionAnalysis> Sections,
    List<CapacityRecommendation> Recommendations);

public record SectionAnalysis(
    string SectionId,
    string SectionName,
    int Capacity,
    int Sold,
    int Available,
    decimal VelocityPerHour,
    decimal AveragePrice,
    TimeSpan EstimatedSellOutTime);

public record CapacityRecommendation(
    AdjustmentType Type,
    string SectionId,
    string Rationale,
    decimal EstimatedRevenueImpact,
    decimal ConfidenceScore);

public record CapacityAdjustment(
    AdjustmentType Type,
    string SectionId,
    Money? NewPrice,
    int? QuantityChange,
    string Reason);

public record AdjustmentResult(
    bool Success,
    string AdjustmentId,
    int TicketsAffected,
    Money RevenueImpact,
    List<string> AffectedTicketIds);

public record DemandMetrics(
    int EventId,
    DateTime Timestamp,
    int PageViewsLastHour,
    int CartAddsLastHour,
    int PurchasesLastHour,
    decimal ConversionRate,
    decimal DemandScore,  // 0-100 scale
    List<SectionDemand> SectionDemands);

public record SectionDemand(
    string SectionId,
    int ViewCount,
    int SelectCount,
    decimal DemandRatio);

public record PricingRecommendation(
    string SectionId,
    Money CurrentPrice,
    Money RecommendedPrice,
    Money PriceFloor,
    Money PriceCeiling,
    decimal ConfidencePercent,
    string Rationale);

public record AccessibleAllocation(
    int EventId,
    List<string> ReservedSeatIds,
    int CompanionSeatsIncluded,
    DateTime AllocationExpiresAt);

public record CapacitySnapshot(
    int EventId,
    DateTime Timestamp,
    int TotalAvailable,
    int RecentSales,
    Dictionary<string, int> AvailabilityBySection);

public record SectionConfiguration(
    string SectionId,
    string SectionName,
    int Rows,
    int SeatsPerRow,
    SeatingType Type,
    Money BasePrice,
    bool IsAccessible);

public record SectionClosure(
    string SectionId,
    int ReservationsAffected,
    List<string> MovedToSection,
    List<string> RefundedTicketIds);

public record SeatingLayout(
    SeatingType Type,
    int? Rows,
    int? SeatsPerRow,
    int? StandingCapacity);

public record ReconfigurationResult(
    bool Success,
    string SectionId,
    SeatingType OldType,
    SeatingType NewType,
    int OldCapacity,
    int NewCapacity);
```

### Architectural Requirements

1. **Project Structure**:
   - Create `src/Optimizer/Optimizer.csproj` referencing `Shared.csproj`
   - Create `src/Optimizer/Controllers/OptimizerController.cs` with REST endpoints
   - Create `src/Optimizer/Program.cs` (port 5012)
   - Create `tests/Optimizer.Tests/Optimizer.Tests.csproj` and `OptimizerTests.cs`

2. **Integration Points**:
   - Read from `IVenueService` for venue layout information
   - Read from `ITicketInventoryService` for current inventory state
   - Publish `SectionOpenedEvent`, `PriceChangedEvent` to `IEventBus`
   - Subscribe to `TicketPurchasedEvent` for real-time demand tracking

3. **Patterns to Follow**:
   - Use `IAsyncEnumerable<T>` with proper cancellation (avoid BUG A5 pattern)
   - Use `decimal` for all pricing calculations (avoid BUG B2 float precision)
   - Avoid client-side evaluation in LINQ (avoid BUG C2 pattern)
   - Use `Channel<T>` for backpressure in streaming (avoid BUG A7 pattern)

4. **Performance Requirements**:
   - Cache demand metrics with TTL using Redis patterns from existing services
   - Use `SemaphoreSlim` for rate limiting concurrent adjustments
   - Implement circuit breaker for external service calls (follow BUG G6 fix pattern)

### Acceptance Criteria

- [ ] 50+ unit tests covering all interface methods
- [ ] Tests for concurrent section adjustments (thread safety)
- [ ] Tests for accessible seating ADA compliance rules
- [ ] Tests for dynamic pricing boundary conditions (floor/ceiling)
- [ ] Tests for streaming cancellation handling
- [ ] Tests for demand metric aggregation accuracy
- [ ] `IAsyncEnumerable` respects `CancellationToken` properly
- [ ] All pricing uses `decimal` type, never `float`
- [ ] Circuit breaker prevents cascade failures
- [ ] Real-time stream has backpressure handling

---

## General Requirements for All Tasks

### Code Quality

1. **Follow existing patterns** from the codebase:
   - Interface-based dependency injection
   - Async/await throughout (no sync-over-async)
   - Nullable reference types enabled
   - XML documentation on all public members

2. **Avoid known bug patterns**:
   - No `Task.Result` or `.Wait()` (BUG A1)
   - No `float` for money (BUG B2)
   - No struct copy bugs (BUG B3)
   - No missing switch cases (BUG K2)
   - No `async void` (BUG A3)
   - Proper `CancellationToken` usage (BUG A5)

3. **Testing requirements**:
   - Use xUnit with `FluentAssertions`
   - Mock dependencies with `Moq`
   - Test both success and failure paths
   - Test boundary conditions and edge cases

### Project File Template

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

### Test Project File Template

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
