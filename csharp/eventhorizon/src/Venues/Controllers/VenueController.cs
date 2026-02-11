using Microsoft.AspNetCore.Mvc;

namespace EventHorizon.Venues.Controllers;

[ApiController]
[Route("api/[controller]")]
public class VenueController : ControllerBase
{
    private readonly Services.IVenueService _venueService;

    public VenueController(Services.IVenueService venueService)
    {
        _venueService = venueService;
    }

    [HttpGet]
    public async Task<IActionResult> GetAll()
    {
        var venues = await _venueService.GetAllVenuesAsync();
        return Ok(venues);
    }

    // === BUG C4: Closure captures loop variable ===
    [HttpGet("search")]
    public async Task<IActionResult> SearchByCapacity([FromQuery] int[] minCapacities)
    {
        var results = new List<List<Services.VenueDto>>();
        var allVenues = await _venueService.GetAllVenuesAsync();

        for (int i = 0; i < minCapacities.Length; i++)
        {
            
            results.Add(allVenues.Where(v => v.Capacity >= minCapacities[i]).ToList());
        }

        return Ok(results);
    }
}
