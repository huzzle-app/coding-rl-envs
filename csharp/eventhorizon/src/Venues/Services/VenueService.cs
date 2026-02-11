using EventHorizon.Shared.Models;
using System.Linq.Expressions;

namespace EventHorizon.Venues.Services;

public interface IVenueService
{
    Task<List<VenueDto>> GetAllVenuesAsync();
    Task<VenueDto?> GetVenueByIdAsync(int id);
    List<VenueDto> FilterVenues(List<VenueDto> venues, Func<VenueDto, bool> predicate);
    List<VenueDto> FilterVenuesExpression(List<VenueDto> venues, Expression<Func<VenueDto, bool>> predicate);
}

public class VenueDto
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public int Capacity { get; set; }
    public string City { get; set; } = "";
    public List<SectionDto> Sections { get; set; } = new();
    public List<EventRef> Events { get; set; } = new();
}

public class SectionDto
{
    public string Name { get; set; } = "";
    public int Rows { get; set; }
    public int SeatsPerRow { get; set; }
}

public class EventRef
{
    public int EventId { get; set; }
    public string EventName { get; set; } = "";
}

public class VenueService : IVenueService
{
    private readonly List<VenueDto> _venues = new()
    {
        new VenueDto
        {
            Id = 1, Name = "Grand Arena", Capacity = 20000, City = "NYC",
            Sections = new() { new SectionDto { Name = "A", Rows = 50, SeatsPerRow = 40 } },
            Events = new() { new EventRef { EventId = 1, EventName = "Concert A" } }
        },
        new VenueDto
        {
            Id = 2, Name = "City Theater", Capacity = 5000, City = "LA",
            Sections = new() { new SectionDto { Name = "Main", Rows = 25, SeatsPerRow = 20 } },
            Events = new() { new EventRef { EventId = 2, EventName = "Concert B" } }
        },
    };

    // === BUG E3: Include cartesian explosion (simulated) ===
    public async Task<List<VenueDto>> GetAllVenuesAsync()
    {
        await Task.Delay(5);
        
        // In real EF Core, this would create a cartesian product
        return _venues.Select(v => new VenueDto
        {
            Id = v.Id, Name = v.Name, Capacity = v.Capacity, City = v.City,
            Sections = v.Sections, Events = v.Events
        }).ToList();
    }

    public async Task<VenueDto?> GetVenueByIdAsync(int id)
    {
        await Task.Delay(5);
        return _venues.FirstOrDefault(v => v.Id == id);
    }

    // === BUG C5: Expression<Func> vs Func - Func can't be translated to SQL ===
    public List<VenueDto> FilterVenues(List<VenueDto> venues, Func<VenueDto, bool> predicate)
    {
        
        return venues.Where(predicate).ToList();
    }

    public List<VenueDto> FilterVenuesExpression(List<VenueDto> venues, Expression<Func<VenueDto, bool>> predicate)
    {
        // Correct: Expression can be translated to SQL by EF Core
        return venues.AsQueryable().Where(predicate).ToList();
    }
}
