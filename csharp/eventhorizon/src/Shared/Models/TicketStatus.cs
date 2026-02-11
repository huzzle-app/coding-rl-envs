namespace EventHorizon.Shared.Models;

public enum TicketStatus
{
    Available = 0,
    Reserved = 1,
    Sold = 2,
    Cancelled = 3,
    Refunded = 4,
    Expired = 5
}

// === BUG K2: Enum switch without exhaustive coverage ===
// When new enum values are added, existing switch expressions
// silently miss them (no compiler warning without default)
public static class TicketStatusHelper
{
    public static string GetDisplayName(TicketStatus status) => status switch
    {
        TicketStatus.Available => "Available",
        TicketStatus.Reserved => "Reserved",
        TicketStatus.Sold => "Sold",
        TicketStatus.Cancelled => "Cancelled",
        TicketStatus.Refunded => "Refunded",
        
        // No default case either, so this throws at runtime for Expired
    };

    // === BUG B6: Boxed enum equality ===
    public static bool CompareStatus(TicketStatus a, TicketStatus b)
    {
        object boxedA = a;
        object boxedB = (int)b; // Boxing as int, not enum
        return boxedA.Equals(boxedB); // Always false! Different boxed types
    }
}

public enum EventStatus
{
    Draft = 0,
    Published = 1,
    OnSale = 2,
    SoldOut = 3,
    Completed = 4,
    Cancelled = 5
}
