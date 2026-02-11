using FluentAssertions;
using HealthLink.Api.Services;
using Xunit;

namespace HealthLink.Tests.Concurrency;

public class ValueTaskTests
{
    [Fact]
    public async Task test_valuetask_not_double_awaited()
    {
        
        var service = new CacheService();
        var result = await service.GetOrCreateAsync("test-key", () => Task.FromResult("test-value"));
        result.Should().Be("test-value");
    }

    [Fact]
    public async Task test_cache_read_safe()
    {
        
        var service = new CacheService();
        await service.SetAsync("existing-key", "cached-value");

        var result = await service.GetOrCreateAsync("existing-key", () => Task.FromResult("new-value"));
        result.Should().Be("cached-value");
    }

    [Fact]
    public async Task test_cache_get_set()
    {
        var service = new CacheService();
        await service.SetAsync("k1", "v1");
        var result = await service.GetAsync("k1");
        result.Should().Be("v1");
    }

    [Fact]
    public async Task test_cache_miss()
    {
        var service = new CacheService();
        var result = await service.GetAsync("nonexistent");
        result.Should().BeNull();
    }

    [Fact]
    public async Task test_cache_expiry()
    {
        var service = new CacheService();
        await service.SetAsync("expiring", "value", TimeSpan.FromMilliseconds(1));
        await Task.Delay(50);
        var result = await service.GetAsync("expiring");
        result.Should().BeNull();
    }
}
