using Microsoft.AspNetCore.Mvc;

namespace EventHorizon.Tickets.Controllers;

[ApiController]
[Route("api/[controller]")]
public class TicketController : ControllerBase
{
    private readonly Services.ITicketInventoryService _ticketService;

    public TicketController(Services.ITicketInventoryService ticketService)
    {
        _ticketService = ticketService;
    }

    [HttpGet("event/{eventId}")]
    public async Task<IActionResult> GetTicketsForEvent(int eventId)
    {
        var tickets = await _ticketService.GetAvailableTicketsAsync(eventId);
        return Ok(tickets);
    }

    [HttpPost("reserve")]
    public async Task<IActionResult> ReserveTicket([FromBody] ReserveRequest request)
    {
        var result = await _ticketService.ReserveTicketAsync(request.EventId, request.SeatId, request.CustomerId);
        return result ? Ok("Reserved") : BadRequest("Failed");
    }
}

public record ReserveRequest(int EventId, string SeatId, string CustomerId);
