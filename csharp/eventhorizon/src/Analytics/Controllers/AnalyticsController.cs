using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace EventHorizon.Analytics.Controllers;

// === BUG J2: IOptions vs IOptionsSnapshot ===
// IOptions<T> is singleton - doesn't reload when config changes
// Should use IOptionsSnapshot<T> for scoped/transient services
public class AnalyticsSettings
{
    public int MaxReportDays { get; set; } = 30;
    public string DefaultCurrency { get; set; } = "USD";
}

[ApiController]
[Route("api/[controller]")]
public class AnalyticsController : ControllerBase
{
    private readonly Services.IAnalyticsService _analyticsService;
    
    private readonly IOptions<AnalyticsSettings> _settings;

    public AnalyticsController(
        Services.IAnalyticsService analyticsService,
        IOptions<AnalyticsSettings> settings)
    {
        _analyticsService = analyticsService;
        _settings = settings;
    }

    [HttpGet("report")]
    public async Task<IActionResult> GetReport([FromQuery] DateTime? from, [FromQuery] DateTime? to)
    {
        var start = from ?? DateTime.UtcNow.AddDays(-_settings.Value.MaxReportDays);
        var end = to ?? DateTime.UtcNow;
        var report = await _analyticsService.GenerateReportAsync(start, end);
        return Ok(report);
    }
}
