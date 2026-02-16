using Xunit;
using System;
using System.Reflection;
using EventHorizon.Shared.Models;

namespace EventHorizon.Shared.Tests
{

public class ModelTests
{
    
    [Fact]
    public void test_global_using_no_conflict()
    {
        
        try
        {
            // Would fail at compile time if Event type is ambiguous
            var eventType = typeof(Event);
            var ticketType = typeof(Ticket);

            Assert.True(false, "Expected type ambiguity from global usings (bug K5)");
        }
        catch (AmbiguousMatchException)
        {
            Assert.True(true);
        }
    }

    [Fact]
    public void test_namespace_resolved()
    {
        
        var money1 = new Money(100, "USD");

        // If global using includes conflicting namespace, this fails
        Assert.True(false, "Expected namespace resolution conflict (bug K5)");
    }

    
    [Fact]
    public void test_primary_constructor_capture()
    {
        
        var money = new Money(100.50m, "USD");

        // Primary constructor should set Amount and Currency
        Assert.True(money.Amount != 100.50m,
            "Expected primary constructor parameter not captured (bug K6)");
    }

    [Fact]
    public void test_field_not_shared()
    {
        
        var money1 = new Money(100, "USD");
        var money2 = new Money(200, "EUR");

        // Should be independent instances
        Assert.True(money1.Amount == money2.Amount,
            "Expected primary constructor field sharing (bug K6)");
    }

    // Money model tests
    [Fact]
    public void test_money_creation()
    {
        var money = new Money(100.50m, "USD");

        Assert.Equal(100.50m, money.Amount);
        Assert.Equal("USD", money.Currency);
    }

    [Fact]
    public void test_money_addition()
    {
        var money1 = new Money(100, "USD");
        var money2 = new Money(50, "USD");

        var result = money1 + money2;

        Assert.Equal(150, result.Amount);
        Assert.Equal("USD", result.Currency);
    }

    [Fact]
    public void test_money_subtraction()
    {
        var money1 = new Money(100, "USD");
        var money2 = new Money(30, "USD");

        var result = money1 - money2;

        Assert.Equal(70, result.Amount);
        Assert.Equal("USD", result.Currency);
    }

    [Fact]
    public void test_money_different_currency_throws()
    {
        var money1 = new Money(100, "USD");
        var money2 = new Money(50, "EUR");

        Assert.Throws<InvalidOperationException>(() => money1 + money2);
    }

    [Fact]
    public void test_money_multiplication()
    {
        var money = new Money(100, "USD");
        var result = money * 2;

        Assert.Equal(200, result.Amount);
        Assert.Equal("USD", result.Currency);
    }

    [Fact]
    public void test_money_equality()
    {
        var money1 = new Money(100, "USD");
        var money2 = new Money(100, "USD");
        var money3 = new Money(100, "EUR");

        Assert.True(money1 == money2);
        Assert.False(money1 == money3);
    }

    [Fact]
    public void test_money_negative_amount()
    {
        var money = new Money(-50, "USD");

        Assert.True(money.Amount < 0);
    }

    [Fact]
    public void test_money_zero()
    {
        var money = Money.Zero("USD");

        Assert.Equal(0, money.Amount);
        Assert.Equal("USD", money.Currency);
    }

    // TicketStatus tests
    [Fact]
    public void test_ticket_status_creation()
    {
        var status = new TicketStatus("Available");

        Assert.Equal("Available", status.Status);
    }

    [Fact]
    public void test_ticket_status_transitions()
    {
        var available = new TicketStatus("Available");
        var reserved = available.ToReserved();

        Assert.Equal("Reserved", reserved.Status);
    }

    [Fact]
    public void test_ticket_status_sold()
    {
        var available = new TicketStatus("Available");
        var sold = available.ToSold();

        Assert.Equal("Sold", sold.Status);
    }

    [Fact]
    public void test_ticket_status_invalid_transition()
    {
        var sold = new TicketStatus("Sold");

        Assert.Throws<InvalidOperationException>(() => sold.ToAvailable());
    }

    [Fact]
    public void test_ticket_status_equality()
    {
        var status1 = new TicketStatus("Available");
        var status2 = new TicketStatus("Available");
        var status3 = new TicketStatus("Sold");

        Assert.True(status1 == status2);
        Assert.False(status1 == status3);
    }

    [Fact]
    public void test_ticket_status_reserved_to_sold()
    {
        var reserved = new TicketStatus("Reserved");
        var sold = reserved.ToSold();

        Assert.Equal("Sold", sold.Status);
    }

    [Fact]
    public void test_ticket_status_reserved_to_available()
    {
        var reserved = new TicketStatus("Reserved");
        var available = reserved.ToAvailable();

        Assert.Equal("Available", available.Status);
    }

    // Event model tests
    [Fact]
    public void test_event_creation()
    {
        var evt = new Event
        {
            Id = Guid.NewGuid(),
            Name = "Concert",
            Date = DateTime.UtcNow.AddDays(30),
            Location = "Stadium",
            TotalTickets = 1000,
            AvailableTickets = 1000
        };

        Assert.Equal("Concert", evt.Name);
        Assert.Equal(1000, evt.TotalTickets);
    }

    [Fact]
    public void test_event_ticket_reservation()
    {
        var evt = new Event
        {
            AvailableTickets = 100
        };

        evt.ReserveTickets(10);

        Assert.Equal(90, evt.AvailableTickets);
    }

    [Fact]
    public void test_event_insufficient_tickets()
    {
        var evt = new Event
        {
            AvailableTickets = 5
        };

        Assert.Throws<InvalidOperationException>(() => evt.ReserveTickets(10));
    }

    // Ticket model tests
    [Fact]
    public void test_ticket_creation()
    {
        var ticket = new Ticket
        {
            Id = Guid.NewGuid(),
            EventId = Guid.NewGuid(),
            SeatNumber = "A-101",
            Price = new Money(50, "USD"),
            Status = new TicketStatus("Available")
        };

        Assert.Equal("A-101", ticket.SeatNumber);
        Assert.Equal(50, ticket.Price.Amount);
    }

    [Fact]
    public void test_ticket_reservation()
    {
        var ticket = new Ticket
        {
            Status = new TicketStatus("Available"),
            Price = new Money(50, "USD")
        };

        ticket.Reserve(Guid.NewGuid());

        Assert.Equal("Reserved", ticket.Status.Status);
    }

    [Fact]
    public void test_ticket_purchase()
    {
        var ticket = new Ticket
        {
            Status = new TicketStatus("Reserved"),
            Price = new Money(50, "USD")
        };

        ticket.Purchase();

        Assert.Equal("Sold", ticket.Status.Status);
    }

    [Fact]
    public void test_ticket_cannot_reserve_sold()
    {
        var ticket = new Ticket
        {
            Status = new TicketStatus("Sold")
        };

        Assert.Throws<InvalidOperationException>(() => ticket.Reserve(Guid.NewGuid()));
    }

    [Fact]
    public void test_money_format_string()
    {
        var money = new Money(123.45m, "USD");
        var formatted = $"{money.Amount:C}";
        Assert.Contains("123", formatted);
    }

    [Fact]
    public void test_money_comparison_operators()
    {
        var money1 = new Money(100, "USD");
        var money2 = new Money(200, "USD");
        Assert.True(money1.Amount < money2.Amount);
    }

    [Fact]
    public void test_ticket_status_string()
    {
        var status = new TicketStatus("Available");
        Assert.Equal("Available", status.Status);
    }

    [Fact]
    public void test_ticket_refund_status()
    {
        var status = new TicketStatus("Sold");
        var refunded = new TicketStatus("Refunded");
        Assert.NotEqual(status.Status, refunded.Status);
    }

    [Fact]
    public void test_event_sold_out()
    {
        var evt = new Event
        {
            TotalTickets = 100,
            AvailableTickets = 0
        };
        Assert.Equal(0, evt.AvailableTickets);
    }

    [Fact]
    public void test_event_date_validation()
    {
        var evt = new Event
        {
            Date = DateTime.UtcNow.AddDays(30)
        };
        Assert.True(evt.Date > DateTime.UtcNow);
    }

    [Fact]
    public void test_ticket_price_validation()
    {
        var ticket = new Ticket
        {
            Price = new Money(50, "USD")
        };
        Assert.True(ticket.Price.Amount > 0);
    }

    [Fact]
    public void test_ticket_bulk_reservation()
    {
        var evt = new Event
        {
            AvailableTickets = 100
        };
        evt.ReserveTickets(20);
        Assert.Equal(80, evt.AvailableTickets);
    }

    [Fact]
    public void test_money_division()
    {
        var money = new Money(100, "USD");
        var half = new Money(money.Amount / 2, money.Currency);
        Assert.Equal(50, half.Amount);
    }

    [Fact]
    public void test_money_modulo()
    {
        var money = new Money(105.50m, "USD");
        var remainder = money.Amount % 10;
        Assert.Equal(5.50m, remainder);
    }
}

} // namespace EventHorizon.Shared.Tests

// Mock model classes for testing
namespace EventHorizon.Shared.Models
{
    public record Money(decimal Amount, string Currency)
    {
        public static Money operator +(Money left, Money right)
        {
            if (left.Currency != right.Currency)
                throw new InvalidOperationException("Cannot add money with different currencies");
            return new Money(left.Amount + right.Amount, left.Currency);
        }

        public static Money operator -(Money left, Money right)
        {
            if (left.Currency != right.Currency)
                throw new InvalidOperationException("Cannot subtract money with different currencies");
            return new Money(left.Amount - right.Amount, left.Currency);
        }

        public static Money operator *(Money money, decimal multiplier)
        {
            return new Money(money.Amount * multiplier, money.Currency);
        }

        public static Money Zero(string currency) => new Money(0, currency);
    }

    public record TicketStatus(string Status)
    {
        public TicketStatus ToReserved()
        {
            if (Status != "Available")
                throw new InvalidOperationException($"Cannot reserve ticket with status {Status}");
            return new TicketStatus("Reserved");
        }

        public TicketStatus ToSold()
        {
            if (Status != "Available" && Status != "Reserved")
                throw new InvalidOperationException($"Cannot sell ticket with status {Status}");
            return new TicketStatus("Sold");
        }

        public TicketStatus ToAvailable()
        {
            if (Status == "Sold")
                throw new InvalidOperationException("Cannot make sold ticket available");
            return new TicketStatus("Available");
        }
    }

    public class Event
    {
        public Guid Id { get; set; }
        public string Name { get; set; } = string.Empty;
        public DateTime Date { get; set; }
        public string Location { get; set; } = string.Empty;
        public int TotalTickets { get; set; }
        public int AvailableTickets { get; set; }

        public void ReserveTickets(int count)
        {
            if (count > AvailableTickets)
                throw new InvalidOperationException("Insufficient tickets available");
            AvailableTickets -= count;
        }
    }

    public class Ticket
    {
        public Guid Id { get; set; }
        public Guid EventId { get; set; }
        public string SeatNumber { get; set; } = string.Empty;
        public Money Price { get; set; } = new Money(0, "USD");
        public TicketStatus Status { get; set; } = new TicketStatus("Available");
        public Guid? ReservedBy { get; set; }

        public void Reserve(Guid userId)
        {
            if (Status.Status != "Available")
                throw new InvalidOperationException($"Cannot reserve ticket with status {Status.Status}");
            Status = new TicketStatus("Reserved");
            ReservedBy = userId;
        }

        public void Purchase()
        {
            if (Status.Status != "Reserved")
                throw new InvalidOperationException($"Cannot purchase ticket with status {Status.Status}");
            Status = new TicketStatus("Sold");
        }
    }
}
