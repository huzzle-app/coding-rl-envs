namespace EventHorizon.Shared.Models;

public record struct Money(float Amount, string Currency)
{
    public static Money operator +(Money a, Money b)
    {
        if (a.Currency != b.Currency)
            throw new InvalidOperationException("Cannot add different currencies");
        return new Money(a.Amount + b.Amount, a.Currency);
    }

    public static Money Zero(string currency = "USD") => new(0f, currency);
}

public record Order(string OrderId, string CustomerId, List<OrderItem> Items, Money Total);

public record OrderItem(string TicketId, string EventName, Money Price, int Quantity);

public struct SeatAssignment
{
    public string Section { get; set; }
    public int Row { get; set; }
    public int Seat { get; set; }
    public bool IsAssigned { get; set; }
}
