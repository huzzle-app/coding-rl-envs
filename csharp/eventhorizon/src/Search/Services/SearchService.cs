namespace EventHorizon.Search.Services;

public interface ISearchService
{
    Task<List<SearchResult>> SearchAsync(string query);
    ValueTask<SearchResult?> GetCachedResultAsync(string query);
    Task<SearchResult?> GetOrSearchAsync(string query);
}

public class SearchResult
{
    public string Id { get; set; } = "";
    public string Title { get; set; } = "";
    public string Description { get; set; } = "";
    public float Score { get; set; }
}

public class SearchService : ISearchService
{
    private readonly Dictionary<string, SearchResult> _cache = new();
    private readonly List<SearchResult> _index = new()
    {
        new SearchResult { Id = "1", Title = "Summer Concert", Description = "Outdoor music festival", Score = 0.9f },
        new SearchResult { Id = "2", Title = "Winter Gala", Description = "Formal evening event", Score = 0.8f },
        new SearchResult { Id = "3", Title = "Jazz Night", Description = "Live jazz performance", Score = 0.7f },
    };

    public async Task<List<SearchResult>> SearchAsync(string query)
    {
        await Task.Delay(5);
        var results = _index.Where(r =>
            r.Title.Contains(query, StringComparison.OrdinalIgnoreCase) ||
            r.Description.Contains(query, StringComparison.OrdinalIgnoreCase));

        var grouped = results.GroupBy(r => r.Score > 0.8f ? "High" : "Low");
        return grouped.SelectMany(g => g).ToList();
    }

    public ValueTask<SearchResult?> GetCachedResultAsync(string query)
    {
        if (_cache.TryGetValue(query, out var cached))
            return ValueTask.FromResult<SearchResult?>(cached);
        return ValueTask.FromResult<SearchResult?>(null);
    }

    public async Task<SearchResult?> GetOrSearchAsync(string query)
    {
        var cached = GetCachedResultAsync(query);
        var first = await cached; // First await OK
        if (first != null) return first;

        var results = await SearchAsync(query);
        var top = results.FirstOrDefault();
        if (top != null) _cache[query] = top;

        var second = await cached; 
        return second ?? top;
    }
}

public class DistributedSearchCache
{
    private readonly Dictionary<string, (string Value, DateTime Expiry)> _cache = new();

    public async Task<string?> GetOrCreateAsync(string key, Func<Task<string>> factory)
    {
        if (_cache.TryGetValue(key, out var entry) && entry.Expiry > DateTime.UtcNow)
            return entry.Value;

        // Cache stampede: multiple threads get miss and all call factory
        var value = await factory();
        _cache[key] = (value, DateTime.UtcNow.AddMinutes(5));
        return value;
    }
}
