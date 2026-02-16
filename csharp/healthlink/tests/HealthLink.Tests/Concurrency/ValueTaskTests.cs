using FluentAssertions;
using HealthLink.Api.Services;
using Xunit;

namespace HealthLink.Tests.Concurrency;

public class ValueTaskTests
{
    [Fact]
    public void test_valuetask_not_double_awaited()
    {
        // Verify that GetOrCreateAsync doesn't await the same ValueTask twice
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Services", "CacheService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // Count how many times 'await cachedValue' appears - should be at most 1
        var matches = System.Text.RegularExpressions.Regex.Matches(source, @"await\s+cachedValue");
        matches.Count.Should().BeLessOrEqualTo(1,
            "ValueTask can only be awaited once; double-await causes undefined behavior");
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
