using Microsoft.AspNetCore.Mvc;

namespace EventHorizon.Events.Controllers;

[ApiController]
[Route("api/[controller]")]
public class EventController : ControllerBase
{
    private readonly Services.IEventManagementService _eventService;

    public EventController(Services.IEventManagementService eventService)
    {
        _eventService = eventService;
    }

    [HttpGet]
    public async Task<IActionResult> GetAll()
    {
        var events = await _eventService.GetAllEventsAsync();
        return Ok(events);
    }

    [HttpGet("{id}")]
    public async Task<IActionResult> GetById(int id)
    {
        var evt = await _eventService.GetEventByIdAsync(id);
        return evt != null ? Ok(evt) : NotFound();
    }
}
