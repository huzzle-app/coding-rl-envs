# QA Report: Data Inconsistency and Serialization Issues

## Test Failure Summary

**Sprint**: 2024-Q1-S6
**Test Run**: Nightly Integration Suite
**Date**: 2024-02-28
**Environment**: staging-us-east-1
**Overall Result**: 127 Failed / 510 Total (75% Pass Rate)

---

## Category 1: Ticket Reservation Failures

### Test: `TicketReservation_ShouldAssignSeatCorrectly`

**Status**: FAILED
**Failure Rate**: 100% (deterministic)

**Test Code**:
```csharp
[Fact]
public async Task TicketReservation_ShouldAssignSeatCorrectly()
{
    var service = new TicketInventoryService();
    var result = await service.ReserveTicketAsync(eventId: 1, seatId: "A-5", customerId: "cust123");

    Assert.True(result); // PASS

    var tickets = await service.GetAvailableTicketsAsync(1);
    var reserved = tickets.First(t => t.SeatId == "A-5");

    // This assertion fails!
    Assert.True(reserved.Seat.IsAssigned,
        $"Expected seat to be assigned. Actual: IsAssigned={reserved.Seat.IsAssigned}");
}
```

**Failure Message**:
```
Expected seat to be assigned. Actual: IsAssigned=False

Stack Trace:
   at TicketTests.TicketReservation_ShouldAssignSeatCorrectly() in TicketTests.cs:line 47
```

**Investigation Notes**:
The `ReserveTicketAsync` method returns `true` indicating success, but the seat's `IsAssigned` property remains `false`. This suggests the assignment is being made to a copy rather than the actual ticket record.

---

### Test: `SeatAssignment_DictionaryLookup`

**Status**: FAILED

**Observation**:
All seat assignments end up under the same dictionary key, causing data to be overwritten:

```csharp
// After reserving seats A-1, A-2, A-3 for different customers:
var assignments = _seatAssignments.Keys.ToList();

// Expected: 3 distinct seat keys
// Actual: 1 key (all stored under default(SeatAssignment))
Assert.Equal(3, assignments.Count); // FAILS: Count is 1
```

---

## Category 2: JSON Serialization Mismatches

### Test: `UserSerialization_RoundTrip`

**Status**: FAILED

**Test Code**:
```csharp
[Fact]
public void UserSerialization_ShouldRoundTrip()
{
    var authService = new AuthService();
    var user = new UserInfo { Id = 1, Email = "test@example.com", Role = "Admin" };

    var json = authService.SerializeUser(user);
    var deserialized = authService.DeserializeUser(json);

    // All these assertions fail!
    Assert.Equal(user.Id, deserialized.Id);         // 0 != 1
    Assert.Equal(user.Email, deserialized.Email);   // null != "test@example.com"
    Assert.Equal(user.Role, deserialized.Role);     // null != "Admin"
}
```

**Failure Message**:
```
Assert.Equal() Failure
Expected: 1
Actual:   0

Serialized JSON: {"Id":1,"Email":"test@example.com","Role":"Admin","DisplayName":""}
Note: JSON uses PascalCase

Deserialization expects camelCase: {"id":1,"email":"...","role":"..."}
```

**Root Cause Hypothesis**:
The `SerializeUser` method uses `PropertyNamingPolicy = null` (PascalCase), but `DeserializeUser` uses default options (camelCase). The property names don't match, so deserialization produces default values.

---

### Test: `CrossService_UserPayload`

**Status**: FAILED

**Description**:
When Auth service sends user data to Orders service, the deserialization fails due to case mismatch:

```
Auth Service -> {"Id":1,"Email":"user@test.com"} -> Orders Service
Orders Service receives: UserInfo { Id = 0, Email = null }
```

---

## Category 3: Search Service Inconsistencies

### Test: `CachedSearch_ShouldReturnConsistentResults`

**Status**: FLAKY (fails ~40% of runs)

**Failure Pattern**:
```
Test iteration 1: PASS
Test iteration 2: FAIL - NullReferenceException
Test iteration 3: PASS
Test iteration 4: FAIL - "Unexpected value returned"
```

**Error Details**:
```
System.InvalidOperationException: ValueTask can only be awaited once.
   at SearchService.GetOrSearchAsync()
```

**Observation**:
The test only fails when cache is populated. The `GetOrSearchAsync` method appears to await the same `ValueTask<SearchResult?>` multiple times.

---

### Test: `DistributedCache_ConcurrentAccess`

**Status**: FAILED

**Test Code**:
```csharp
[Fact]
public async Task ConcurrentAccess_ShouldNotCallFactoryMultipleTimes()
{
    var cache = new DistributedSearchCache();
    var factoryCallCount = 0;

    var tasks = Enumerable.Range(0, 100).Select(_ =>
        cache.GetOrCreateAsync("key", async () =>
        {
            Interlocked.Increment(ref factoryCallCount);
            await Task.Delay(100); // Simulate slow operation
            return "value";
        }));

    await Task.WhenAll(tasks);

    // Factory should only be called once
    Assert.Equal(1, factoryCallCount); // FAILS: factoryCallCount is 87
}
```

**Failure Message**:
```
Assert.Equal() Failure
Expected: 1
Actual:   87
```

---

## Category 4: Enum Comparison Issues

### Test: `TicketStatusFilter_ShouldFilterCorrectly`

**Status**: FAILED

**Test Code**:
```csharp
[Fact]
public void FilterByStatus_ShouldReturnMatchingTickets()
{
    var service = new TicketInventoryService();
    var tickets = new List<TicketInfo>
    {
        new() { Status = TicketStatus.Available },
        new() { Status = TicketStatus.Reserved },
        new() { Status = TicketStatus.Available },
    };

    var available = service.FilterByStatus(tickets, TicketStatus.Available);

    Assert.Equal(2, available.Count); // Sometimes returns 0 or 3
}
```

**Investigation**:
The `FilterByStatus` method uses nullable enum comparison with int casting:
```csharp
TicketStatus? nullableStatus = t.Status;
return ((int?)nullableStatus) == (int)status;
```

This comparison behaves unexpectedly when the nullable value is boxed.

---

## Category 5: Record Equality Issues

### Test: `OrderComparison_ShouldMatchOnContent`

**Status**: FAILED (reported by Payments team)

**Description**:
When comparing orders to detect duplicates, orders with identical content but different collection instances are treated as different:

```csharp
record Order(string Id, List<string> Items);

var order1 = new Order("ORD-1", new List<string> { "TKT-A", "TKT-B" });
var order2 = new Order("ORD-1", new List<string> { "TKT-A", "TKT-B" });

Assert.True(order1 == order2); // FAILS! Lists are reference-compared
```

**Impact**:
Duplicate detection logic fails because record equality doesn't compare collection contents.

---

## Summary Statistics

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| Ticket Reservation | 45 | 32 | 13 |
| JSON Serialization | 38 | 21 | 17 |
| Search Service | 52 | 38 | 14 |
| Enum/Nullable | 23 | 15 | 8 |
| Record Equality | 12 | 5 | 7 |
| Other | 340 | 272 | 68 |

---

## Services Affected

- `Tickets` - Struct value semantics, seat assignment
- `Auth` - JSON serialization configuration
- `Search` - ValueTask handling, cache concurrency
- `Shared` - Record types with collections

## Patterns to Review

1. **Struct copy semantics**: Modifying struct through property creates copy
2. **Default struct as dictionary key**: All lookups resolve to same key
3. **JSON case sensitivity**: System.Text.Json naming policy consistency
4. **ValueTask multiple await**: Can only await once
5. **Record collection equality**: Reference comparison, not content
6. **Nullable lifted operators**: Boxing behavior with enums

---

**Report Generated By**: CI/CD Pipeline
**Reviewed By**: QA Lead @testing-team
**Follow-up**: Sprint retrospective scheduled for 2024-03-01
