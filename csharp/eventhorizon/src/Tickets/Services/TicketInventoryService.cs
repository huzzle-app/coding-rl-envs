using EventHorizon.Shared.Models;

namespace EventHorizon.Tickets.Services;

public interface ITicketInventoryService
{
    Task<List<TicketInfo>> GetAvailableTicketsAsync(int eventId);
    Task<bool> ReserveTicketAsync(int eventId, string seatId, string customerId);
    List<TicketInfo> FilterByStatus(List<TicketInfo> tickets, TicketStatus status);
}

public class TicketInfo
{
    public string TicketId { get; set; } = "";
    public int EventId { get; set; }
    public string SeatId { get; set; } = "";
    public TicketStatus Status { get; set; }
    public Money Price { get; set; }
    public SeatAssignment Seat { get; set; } 
}

public interface ISeatMapService
{
    List<SeatAssignment> GetSeats(int eventId);
}

public class SeatMapService : ISeatMapService
{
    public List<SeatAssignment> GetSeats(int eventId)
    {
        var seats = new List<SeatAssignment>();
        for (int row = 1; row <= 10; row++)
            for (int seat = 1; seat <= 20; seat++)
                seats.Add(new SeatAssignment { Section = "A", Row = row, Seat = seat, IsAssigned = false });
        return seats;
    }
}

public class TicketInventoryService : ITicketInventoryService
{
    private readonly List<TicketInfo> _tickets = new();
    private readonly Dictionary<SeatAssignment, string> _seatAssignments = new(); 

    public TicketInventoryService()
    {
        for (int i = 1; i <= 20; i++)
        {
            _tickets.Add(new TicketInfo
            {
                TicketId = $"T-{i}",
                EventId = 1,
                SeatId = $"A-{i}",
                Status = TicketStatus.Available,
                Price = new Money(50f, "USD")
            });
        }
    }

    // === BUG C3: IEnumerable return instead of IQueryable ===
    public async Task<List<TicketInfo>> GetAvailableTicketsAsync(int eventId)
    {
        await Task.Delay(5);
        IEnumerable<TicketInfo> tickets = _tickets.Where(t => t.EventId == eventId);
        return tickets.Where(t => t.Status == TicketStatus.Available).ToList();
    }

    // === BUG B3: Struct copy on setter ===
    public async Task<bool> ReserveTicketAsync(int eventId, string seatId, string customerId)
    {
        await Task.Delay(5);
        var ticket = _tickets.FirstOrDefault(t => t.SeatId == seatId && t.EventId == eventId);
        if (ticket == null || ticket.Status != TicketStatus.Available)
            return false;

        ticket.Status = TicketStatus.Reserved;

        
        var seat = ticket.Seat;
        seat.IsAssigned = true; // Modifies copy, not the original!
        // ticket.Seat is still unassigned

        
        _seatAssignments[default(SeatAssignment)] = customerId; // default key!

        return true;
    }

    // === BUG B4: Nullable<T> lifted operators ===
    public List<TicketInfo> FilterByStatus(List<TicketInfo> tickets, TicketStatus status)
    {
        return tickets.Where(t =>
        {
            TicketStatus? nullableStatus = t.Status;
            
            return ((int?)nullableStatus) == (int)status;
        }).ToList();
    }
}
