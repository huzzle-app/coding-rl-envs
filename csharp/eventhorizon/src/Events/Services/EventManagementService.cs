using EventHorizon.Shared.Models;
using System.Text.Json;

namespace EventHorizon.Events.Services;

public interface IEventManagementService
{
    Task<List<EventDto>> GetAllEventsAsync();
    Task<EventDto?> GetEventByIdAsync(int id);
    Task<EventDto> CreateEventAsync(EventDto dto);
}

public class EventDto
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Venue { get; set; } = "";
    public DateTime Date { get; set; }
    public EventStatus Status { get; set; }
    public int Capacity { get; set; }
    public Address? Location { get; set; }
}

public class Address
{
    public string Street { get; set; } = "";
    public string City { get; set; } = "";
    public string State { get; set; } = "";
}

public class EventManagementService : IEventManagementService
{
    private readonly List<EventDto> _events = new()
    {
        new EventDto { Id = 1, Name = "Concert A", Venue = "Arena 1", Date = DateTime.UtcNow.AddDays(30), Status = EventStatus.OnSale, Capacity = 5000 },
        new EventDto { Id = 2, Name = "Concert B", Venue = "Arena 2", Date = DateTime.UtcNow.AddDays(60), Status = EventStatus.Published, Capacity = 3000 },
    };

    // === BUG C1: Deferred execution - IEnumerable enumerated multiple times ===
    public async Task<List<EventDto>> GetAllEventsAsync()
    {
        await Task.Delay(5);
        IEnumerable<EventDto> active = _events.Where(e => e.Status != EventStatus.Cancelled);
        var count = active.Count(); // First enumeration
        Console.WriteLine($"Found {count} active events");
        return active.ToList(); // Second enumeration
    }

    // === BUG E1: No change tracker clearing (simulated with stale cache) ===
    private EventDto? _cachedEvent;

    public async Task<EventDto?> GetEventByIdAsync(int id)
    {
        await Task.Delay(5);
        
        if (_cachedEvent?.Id == id) return _cachedEvent;
        _cachedEvent = _events.FirstOrDefault(e => e.Id == id);
        return _cachedEvent;
    }

    // === BUG C2: Client-side evaluation (simulated) ===
    public async Task<EventDto> CreateEventAsync(EventDto dto)
    {
        await Task.Delay(5);
        
        var json = JsonSerializer.Serialize(dto);
        var deserialized = JsonSerializer.Deserialize<EventDto>(json);
        // If Name was null during deserialization, null! hides it
        dto.Id = _events.Count + 1;
        _events.Add(dto);
        return dto;
    }
}
