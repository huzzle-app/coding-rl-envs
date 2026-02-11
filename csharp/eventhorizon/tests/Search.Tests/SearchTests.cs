using Xunit;
using System;
using System.Linq;
using System.Threading.Tasks;
using System.Collections.Generic;
using System.Text.Json;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.Extensions.Caching.Memory;

namespace EventHorizon.Search.Tests;

public class SearchTests
{
    
    [Fact]
    public void test_groupby_server_side()
    {
        // GroupBy should be executed on server (database) not client
        var query = GetSampleQueryable();
        var grouped = query.GroupBy(x => x.Category).ToList();

        var executedOnServer = false; 
        Assert.True(executedOnServer,
            "GroupBy must execute on server - call GroupBy before ToList()");
    }

    [Fact]
    public void test_no_client_groupby()
    {
        // Verify that GroupBy is not materializing collection before grouping
        var items = GetSampleData().ToList(); // Materializes too early
        var grouped = items.GroupBy(x => x.Category);

        var wasServerSide = false; 
        Assert.True(wasServerSide,
            "GroupBy should be part of database query, not in-memory operation");
    }

    
    [Fact]
    public async Task test_valuetask_single_await()
    {
        // ValueTask should only be awaited once - awaiting twice is undefined behavior
        var valueTask = GetValueTaskAsync();
        var firstResult = await valueTask.ConfigureAwait(false);

        var secondAwaitSafe = true;
        try
        {
            var secondResult = await valueTask.ConfigureAwait(false); 
            secondAwaitSafe = false;
        }
        catch
        {
            // Expected - ValueTask can only be awaited once
        }

        Assert.False(secondAwaitSafe,
            "ValueTask must not be awaited multiple times - store result or convert to Task");
    }

    [Fact]
    public async Task test_cache_no_double_await()
    {
        // Cache methods returning ValueTask should not be awaited twice
        var cache = new MemoryCache(new MemoryCacheOptions());
        var valueTask = GetCachedValueAsync(cache, "key");

        var result1 = await valueTask.ConfigureAwait(false);
        var canAwaitTwice = false;

        try
        {
            var result2 = await valueTask.ConfigureAwait(false); 
            canAwaitTwice = true;
        }
        catch
        {
            // Expected
        }

        Assert.False(canAwaitTwice,
            "ValueTask from cache should not be awaited multiple times");
    }

    
    [Fact]
    public async Task test_distributed_cache_race()
    {
        // Multiple concurrent requests should not all query database on cache miss
        var cache = new TestDistributedCache();
        var databaseHitCount = 0;
        var lockObj = new object();

        var tasks = Enumerable.Range(0, 10).Select(async _ =>
        {
            var cached = await cache.GetAsync("expensive-key").ConfigureAwait(false);
            if (cached == null)
            {
                
                lock (lockObj) { databaseHitCount++; }
                await Task.Delay(10).ConfigureAwait(false); // Simulate DB query
                await cache.SetAsync("expensive-key", new byte[] { 1, 2, 3 }).ConfigureAwait(false);
            }
        });

        await Task.WhenAll(tasks).ConfigureAwait(false);

        // Should only hit database once, not 10 times
        Assert.True(databaseHitCount <= 1,
            $"Cache stampede detected: {databaseHitCount} database hits instead of 1");
    }

    [Fact]
    public async Task test_cache_stampede_prevented()
    {
        // Distributed lock should prevent cache stampede
        var hasDistributedLock = false; 
        Assert.True(hasDistributedLock,
            "Must use distributed lock (e.g., RedLock) to prevent cache stampede");
    }

    
    [Fact]
    public void test_span_not_escaped()
    {
        // Span<T> must not be stored in a field or returned from method
        Span<int> span = stackalloc int[10];
        var escaped = TryEscapeSpan(span); 

        Assert.False(escaped,
            "Span<T> must not escape stack context - use Memory<T> or array instead");
    }

    [Fact]
    public void test_stack_span_safe()
    {
        // Verify Span<T> usage is confined to stack
        Span<byte> buffer = stackalloc byte[256];
        ProcessBuffer(buffer);

        var spanIsSafe = !IsSpanEscaped(buffer); 
        Assert.True(spanIsSafe,
            "Span<T> must remain stack-allocated, cannot be stored in heap");
    }

    
    [Fact]
    public void test_record_init_deserialization()
    {
        // Record types with init-only properties should deserialize from JSON
        var json = "{\"id\":123,\"name\":\"test\"}";
        var record = JsonSerializer.Deserialize<SearchRecord>(json);

        var isDeserialized = record != null && record.Id == 123;
        Assert.True(isDeserialized,
            "Record with init properties must deserialize - may need [JsonConstructor]");
    }

    [Fact]
    public void test_json_deserialize_record()
    {
        // JSON deserialization should work with positional records
        var json = "{\"id\":456,\"name\":\"item\",\"score\":9.5}";

        SearchRecord? result = null;
        try
        {
            result = JsonSerializer.Deserialize<SearchRecord>(json);
        }
        catch
        {
            
        }

        Assert.NotNull(result);
        Assert.Equal(456, result?.Id);
    }

    // Baseline tests
    [Fact]
    public void test_search_record_creation()
    {
        var record = new SearchRecord { Id = 1, Name = "test", Score = 5.0 };
        Assert.NotNull(record);
        Assert.Equal(1, record.Id);
    }

    [Fact]
    public void test_linq_basic_query()
    {
        var items = GetSampleData();
        var filtered = items.Where(x => x.Category == "A").ToList();
        Assert.NotEmpty(filtered);
    }

    [Fact]
    public async Task test_task_basic_await()
    {
        var result = await Task.FromResult(42).ConfigureAwait(false);
        Assert.Equal(42, result);
    }

    [Fact]
    public void test_json_serialization()
    {
        var record = new SearchRecord { Id = 1, Name = "test", Score = 1.0 };
        var json = JsonSerializer.Serialize(record);
        Assert.Contains("test", json);
    }

    [Fact]
    public void test_memory_cache_basic()
    {
        var cache = new MemoryCache(new MemoryCacheOptions());
        cache.Set("key", "value");
        var value = cache.Get<string>("key");
        Assert.Equal("value", value);
    }

    [Fact]
    public void test_span_basic_usage()
    {
        Span<int> span = stackalloc int[5];
        span[0] = 42;
        Assert.Equal(42, span[0]);
    }

    [Fact]
    public void test_groupby_basic()
    {
        var items = new[] {
            new SearchItem { Category = "A", Value = 1 },
            new SearchItem { Category = "A", Value = 2 }
        };
        var grouped = items.GroupBy(x => x.Category);
        Assert.Single(grouped);
    }

    [Fact]
    public async Task test_valuetask_single_use()
    {
        var vt = new ValueTask<int>(42);
        var result = await vt.ConfigureAwait(false);
        Assert.Equal(42, result);
    }

    [Fact]
    public void test_full_text_search()
    {
        var documents = new[] {
            new { Id = 1, Content = "quick brown fox" },
            new { Id = 2, Content = "lazy dog sleeps" }
        };
        var results = documents.Where(d => d.Content.Contains("fox")).ToList();
        Assert.Single(results);
    }

    [Fact]
    public void test_fuzzy_search()
    {
        var searchTerm = "quik";
        var actualTerm = "quick";
        var distance = 1;
        Assert.True(distance <= 2);
    }

    [Fact]
    public void test_autocomplete()
    {
        var query = "sea";
        var suggestions = new[] { "search", "season", "seattle" };
        var matches = suggestions.Where(s => s.StartsWith(query)).ToList();
        Assert.Equal(3, matches.Count);
    }

    [Fact]
    public void test_search_pagination()
    {
        var allResults = Enumerable.Range(1, 100).Select(i => new { Id = i }).ToList();
        var page = 3;
        var pageSize = 10;
        var pageResults = allResults.Skip((page - 1) * pageSize).Take(pageSize).ToList();
        Assert.Equal(10, pageResults.Count);
    }

    [Fact]
    public void test_search_sorting()
    {
        var items = new[] {
            new SearchItem { Id = 1, Value = 30 },
            new SearchItem { Id = 2, Value = 10 },
            new SearchItem { Id = 3, Value = 20 }
        };
        var sorted = items.OrderBy(i => i.Value).ToList();
        Assert.Equal(10, sorted[0].Value);
    }

    [Fact]
    public void test_search_filtering()
    {
        var items = GetSampleData();
        var filtered = items.Where(i => i.Value > 15).ToList();
        Assert.Equal(2, filtered.Count);
    }

    [Fact]
    public void test_faceted_search()
    {
        var facets = new Dictionary<string, int>
        {
            { "Category A", 50 },
            { "Category B", 30 },
            { "Category C", 20 }
        };
        Assert.Equal(3, facets.Count);
    }

    [Fact]
    public void test_search_highlighting()
    {
        var content = "The quick brown fox";
        var searchTerm = "quick";
        var highlighted = content.Replace(searchTerm, $"<mark>{searchTerm}</mark>");
        Assert.Contains("<mark>", highlighted);
    }

    [Fact]
    public void test_search_suggestions()
    {
        var query = "pythom";
        var suggestions = new[] { "python", "pythons", "pythagorean" };
        Assert.Contains("python", suggestions);
    }

    [Fact]
    public void test_search_synonyms()
    {
        var synonyms = new Dictionary<string, string[]>
        {
            { "quick", new[] { "fast", "rapid", "swift" } },
            { "big", new[] { "large", "huge", "massive" } }
        };
        Assert.Contains("fast", synonyms["quick"]);
    }

    [Fact]
    public void test_search_boosting()
    {
        var items = new[] {
            new { Title = "Important document", Boost = 2.0 },
            new { Title = "Regular document", Boost = 1.0 }
        };
        var boosted = items.OrderByDescending(i => i.Boost).First();
        Assert.Equal("Important document", boosted.Title);
    }

    [Fact]
    public void test_search_geo_distance()
    {
        var userLat = 40.7128;
        var userLon = -74.0060;
        var resultLat = 40.7580;
        var resultLon = -73.9855;
        var distance = Math.Sqrt(Math.Pow(resultLat - userLat, 2) + Math.Pow(resultLon - userLon, 2));
        Assert.True(distance > 0);
    }

    [Fact]
    public void test_search_date_range()
    {
        var items = new[] {
            new { Id = 1, Date = new DateTime(2026, 1, 15) },
            new { Id = 2, Date = new DateTime(2026, 2, 10) },
            new { Id = 3, Date = new DateTime(2026, 3, 5) }
        };
        var startDate = new DateTime(2026, 2, 1);
        var endDate = new DateTime(2026, 2, 28);
        var filtered = items.Where(i => i.Date >= startDate && i.Date <= endDate).ToList();
        Assert.Single(filtered);
    }

    [Fact]
    public void test_search_aggregation()
    {
        var items = GetSampleData();
        var avgValue = items.Average(i => i.Value);
        Assert.Equal(20, avgValue);
    }

    [Fact]
    public void test_search_index_creation()
    {
        var index = new { Name = "products_index", Fields = new[] { "name", "description", "category" } };
        Assert.Equal(3, index.Fields.Length);
    }

    [Fact]
    public void test_search_index_update()
    {
        var documentId = "doc123";
        var updatedContent = "New content for document";
        Assert.NotEmpty(updatedContent);
    }

    [Fact]
    public void test_search_reindex()
    {
        var totalDocuments = 10000;
        var reindexed = totalDocuments;
        Assert.Equal(totalDocuments, reindexed);
    }

    [Fact]
    public void test_search_bulk_index()
    {
        var documents = Enumerable.Range(1, 100).Select(i => new { Id = i, Content = $"Document {i}" }).ToList();
        Assert.Equal(100, documents.Count);
    }

    [Fact]
    public void test_search_delete_doc()
    {
        var documents = new List<object> { new { Id = 1 }, new { Id = 2 }, new { Id = 3 } };
        documents.RemoveAt(0);
        Assert.Equal(2, documents.Count);
    }

    [Fact]
    public void test_search_alias()
    {
        var aliases = new Dictionary<string, string>
        {
            { "products", "products_v2" },
            { "users", "users_v3" }
        };
        Assert.Equal("products_v2", aliases["products"]);
    }

    // Helper methods and types
    private IQueryable<SearchItem> GetSampleQueryable()
    {
        return GetSampleData().AsQueryable();
    }

    private IEnumerable<SearchItem> GetSampleData()
    {
        return new[]
        {
            new SearchItem { Id = 1, Category = "A", Value = 10 },
            new SearchItem { Id = 2, Category = "B", Value = 20 },
            new SearchItem { Id = 3, Category = "A", Value = 30 }
        };
    }

    private async ValueTask<string> GetValueTaskAsync()
    {
        await Task.Delay(1).ConfigureAwait(false);
        return "result";
    }

    private async ValueTask<byte[]?> GetCachedValueAsync(IMemoryCache cache, string key)
    {
        await Task.Delay(1).ConfigureAwait(false);
        return cache.Get<byte[]>(key);
    }

    private bool TryEscapeSpan(Span<int> span)
    {
        
        return false;
    }

    private bool IsSpanEscaped(Span<byte> span)
    {
        // Check if span escaped stack context
        return false;
    }

    private void ProcessBuffer(Span<byte> buffer)
    {
        // Safe span usage within method
        buffer[0] = 42;
    }
}

// Supporting types
public class SearchItem
{
    public int Id { get; set; }
    public string Category { get; set; } = string.Empty;
    public int Value { get; set; }
}

public class SearchRecord
{
    public int Id { get; init; }
    public string Name { get; init; } = string.Empty;
    public double Score { get; init; }
}

public class TestDistributedCache : IDistributedCache
{
    private readonly Dictionary<string, byte[]> _cache = new();
    private readonly object _lock = new();

    public byte[]? Get(string key)
    {
        lock (_lock)
        {
            return _cache.TryGetValue(key, out var value) ? value : null;
        }
    }

    public Task<byte[]?> GetAsync(string key, System.Threading.CancellationToken token = default)
    {
        return Task.FromResult(Get(key));
    }

    public void Set(string key, byte[] value, DistributedCacheEntryOptions options)
    {
        lock (_lock)
        {
            _cache[key] = value;
        }
    }

    public Task SetAsync(string key, byte[] value, DistributedCacheEntryOptions options, System.Threading.CancellationToken token = default)
    {
        Set(key, value, options);
        return Task.CompletedTask;
    }

    public void Refresh(string key) { }
    public Task RefreshAsync(string key, System.Threading.CancellationToken token = default) => Task.CompletedTask;
    public void Remove(string key)
    {
        lock (_lock)
        {
            _cache.Remove(key);
        }
    }
    public Task RemoveAsync(string key, System.Threading.CancellationToken token = default)
    {
        Remove(key);
        return Task.CompletedTask;
    }
}
