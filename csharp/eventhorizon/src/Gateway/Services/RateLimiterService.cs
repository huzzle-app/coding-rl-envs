namespace EventHorizon.Gateway.Services;

public interface IRateLimiterService
{
    bool IsAllowed(string clientId);
    void Configure(int maxRequests, TimeSpan window);
}

public class RateLimiterService : IRateLimiterService
{
    private readonly Dictionary<string, List<DateTime>> _requests = new();
    // === BUG I7: Rate limiter disabled by default ===
    // maxRequests is set to int.MaxValue, effectively disabling rate limiting
    private int _maxRequests = int.MaxValue;
    private TimeSpan _window = TimeSpan.FromMinutes(1);

    public bool IsAllowed(string clientId)
    {
        if (!_requests.ContainsKey(clientId))
            _requests[clientId] = new List<DateTime>();

        var now = DateTime.UtcNow;
        _requests[clientId].RemoveAll(t => t < now - _window);

        if (_requests[clientId].Count >= _maxRequests)
            return false;

        _requests[clientId].Add(now);
        return true;
    }

    public void Configure(int maxRequests, TimeSpan window)
    {
        _maxRequests = maxRequests;
        _window = window;
    }
}
