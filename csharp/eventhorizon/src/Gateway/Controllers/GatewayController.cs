using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EventHorizon.Gateway.Controllers;

[ApiController]
[Route("api/[controller]")]
public class GatewayController : ControllerBase
{
    private readonly IServiceProvider _serviceProvider;

    public GatewayController(IServiceProvider serviceProvider)
    {
        _serviceProvider = serviceProvider;
    }

    [HttpGet("health")]
    public IActionResult HealthCheck() => Ok(new { Status = "Healthy" });

    [HttpGet("events")]
    public async Task<IActionResult> GetEvents()
    {
        
        var result = GetEventsInternalAsync().Result;
        return Ok(result);
    }

    private async Task<List<string>> GetEventsInternalAsync()
    {
        await Task.Delay(10);
        return new List<string> { "Event1", "Event2" };
    }
}
