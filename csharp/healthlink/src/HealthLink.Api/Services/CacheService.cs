namespace HealthLink.Api.Services;

public interface ICacheService
{
    ValueTask<string?> GetAsync(string key);
    Task SetAsync(string key, string value, TimeSpan? expiry = null);
    Task<string> GetOrCreateAsync(string key, Func<Task<string>> factory);
}

public class CacheService : ICacheService
{
    private readonly Dictionary<string, (string Value, DateTime Expiry)> _cache = new();

    public ValueTask<string?> GetAsync(string key)
    {
        if (_cache.TryGetValue(key, out var entry) && entry.Expiry > DateTime.UtcNow)
        {
            return ValueTask.FromResult<string?>(entry.Value);
        }
        return ValueTask.FromResult<string?>(null);
    }

    public Task SetAsync(string key, string value, TimeSpan? expiry = null)
    {
        var expiryTime = expiry.HasValue
            ? DateTime.UtcNow.Add(expiry.Value)
            : DateTime.UtcNow.AddHours(1);

        _cache[key] = (value, expiryTime);
        return Task.CompletedTask;
    }

    public async Task<string> GetOrCreateAsync(string key, Func<Task<string>> factory)
    {
        var cachedValue = GetAsync(key);

        var firstCheck = await cachedValue;
        if (firstCheck != null)
            return firstCheck;

        var newValue = await factory();
        await SetAsync(key, newValue);

        var secondCheck = await cachedValue;
        return secondCheck ?? newValue;
    }
}
