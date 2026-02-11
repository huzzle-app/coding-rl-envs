using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EventHorizon.Orders.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class OrderController : ControllerBase
{
    private readonly Services.IOrderService _orderService;

    public OrderController(Services.IOrderService orderService)
    {
        _orderService = orderService;
    }

    [HttpPost]
    public async Task<IActionResult> CreateOrder([FromBody] CreateOrderRequest request)
    {
        var order = await _orderService.CreateOrderAsync(request.CustomerId, request.TicketIds);
        return order != null ? Ok(order) : BadRequest("Order failed");
    }

    [HttpGet("{id}")]
    public async Task<IActionResult> GetOrder(string id)
    {
        var order = await _orderService.GetOrderAsync(id);
        return order != null ? Ok(order) : NotFound();
    }
}

public record CreateOrderRequest(string CustomerId, List<string> TicketIds);
