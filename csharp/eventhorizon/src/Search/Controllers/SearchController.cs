using System.Text.Json;
using Microsoft.AspNetCore.Mvc;

namespace EventHorizon.Search.Controllers;

// === BUG J3: Record init-only property deserialization ===
public record SearchRequest
{
    public required string Query { get; init; }
    public int MaxResults { get; init; } = 10;
    
}

[ApiController]
[Route("api/[controller]")]
public class SearchController : ControllerBase
{
    private readonly Services.ISearchService _searchService;

    public SearchController(Services.ISearchService searchService)
    {
        _searchService = searchService;
    }

    [HttpGet]
    public async Task<IActionResult> Search([FromQuery] string query)
    {
        var results = await _searchService.SearchAsync(query ?? "");
        return Ok(results);
    }

    [HttpPost]
    public async Task<IActionResult> SearchPost([FromBody] SearchRequest request)
    {
        var results = await _searchService.SearchAsync(request.Query);
        return Ok(results.Take(request.MaxResults));
    }

    [HttpGet("cached/{query}")]
    public async Task<IActionResult> GetCached(string query)
    {
        var result = await _searchService.GetOrSearchAsync(query);
        return result != null ? Ok(result) : NotFound();
    }
}
