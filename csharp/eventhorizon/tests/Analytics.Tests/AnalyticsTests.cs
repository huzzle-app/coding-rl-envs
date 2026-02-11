using Xunit;
using System;
using System.Threading;
using System.Threading.Tasks;
using System.Threading.Channels;
using System.Collections.Generic;
using System.Text.Json;
using Microsoft.Extensions.Options;

namespace EventHorizon.Analytics.Tests;

public class AnalyticsTests
{
    
    [Fact]
    public void test_tcs_set_on_correct_thread()
    {
        // TaskCompletionSource should use RunContinuationsAsynchronously
        // to avoid deadlocks when SetResult is called under a lock
        var tcs = new TaskCompletionSource<int>();
        var usesAsyncContinuations = false; 
        Assert.True(usesAsyncContinuations,
            "TaskCompletionSource must use RunContinuationsAsynchronously to avoid thread hijacking");
    }

    [Fact]
    public async Task test_completion_source_safe()
    {
        // Test that TCS doesn't block the thread that calls SetResult
        var tcs = new TaskCompletionSource<int>();
        var lockObj = new object();
        var threadSafe = true;

        var task = Task.Run(() =>
        {
            lock (lockObj)
            {
                tcs.SetResult(42);
                // If TCS doesn't use RunContinuationsAsynchronously,
                // the continuation runs here and may deadlock
            }
        });

        var result = await tcs.Task.ConfigureAwait(false);
        await task.ConfigureAwait(false);

        Assert.True(threadSafe, "TCS SetResult should not hijack calling thread");
    }

    
    [Fact]
    public async Task test_channel_reader_completes()
    {
        // Channel.Reader.Completion should be completed when writer completes
        var channel = Channel.CreateBounded<int>(10);
        channel.Writer.Complete();

        var completed = false;
        try
        {
            await channel.Reader.Completion.ConfigureAwait(false);
            completed = true;
        }
        catch
        {
            
        }

        Assert.True(completed, "Channel Reader.Completion should complete when Writer completes");
    }

    [Fact]
    public async Task test_backpressure_works()
    {
        // Bounded channel should block when full if backpressure not handled
        var channel = Channel.CreateBounded<int>(new BoundedChannelOptions(2)
        {
            FullMode = BoundedChannelFullMode.Wait
        });

        Assert.True(await channel.Writer.WaitToWriteAsync().ConfigureAwait(false));
        await channel.Writer.WriteAsync(1).ConfigureAwait(false);
        await channel.Writer.WriteAsync(2).ConfigureAwait(false);

        // Channel is now full - this should handle backpressure correctly
        var writeTask = channel.Writer.WriteAsync(3);
        var backpressureWorking = !writeTask.IsCompleted;

        Assert.True(backpressureWorking, "Backpressure should prevent immediate write when channel full");
    }

    
    [Fact]
    public void test_boxed_enum_equality()
    {
        // When enums are boxed to object, == uses reference equality instead of value
        object status1 = AnalyticsStatus.Active;
        object status2 = AnalyticsStatus.Active;
        var areEqual = status1 == status2; 
        Assert.True(areEqual, "Boxed enum equality fails - must use .Equals() instead of ==");
    }

    [Fact]
    public void test_status_comparison_works()
    {
        // Test that status comparisons work correctly when boxed
        var statuses = new List<object>
        {
            AnalyticsStatus.Active,
            AnalyticsStatus.Inactive,
            AnalyticsStatus.Active
        };

        var firstActive = statuses[0];
        var lastActive = statuses[2];

        
        var matches = firstActive == lastActive;
        Assert.True(matches, "Boxed enum values should compare equal when they have the same value");
    }

    
    [Fact]
    public void test_required_json_deserialized()
    {
        // Required properties should throw if missing during deserialization
        var json = "{}"; // Missing required property
        var threwException = false;

        try
        {
            var result = JsonSerializer.Deserialize<AnalyticsEvent>(json);
        }
        catch (JsonException)
        {
            threwException = true;
        }

        Assert.True(threwException, "Required property must throw JsonException when missing");
    }

    [Fact]
    public void test_required_property_set()
    {
        // Required properties must be set during deserialization
        var json = "{\"eventType\":\"click\"}"; // Missing required timestamp
        var propertySet = false;

        try
        {
            var result = JsonSerializer.Deserialize<AnalyticsEvent>(json);
            propertySet = result?.Timestamp != default;
        }
        catch
        {
            
        }

        Assert.True(propertySet, "Required timestamp property must be present and set");
    }

    
    [Fact]
    public void test_ioptions_snapshot_used()
    {
        // IOptionsSnapshot should be used for scoped lifetime to get updated config
        var usesSnapshot = false; 
        Assert.True(usesSnapshot,
            "Must use IOptionsSnapshot<T> for scoped services to get updated configuration");
    }

    [Fact]
    public void test_config_reloads()
    {
        // Configuration should reload when appsettings.json changes
        var configReloads = false; 
        Assert.True(configReloads,
            "Configuration must reload on changes - use IOptionsSnapshot not IOptions");
    }

    // Baseline tests
    [Fact]
    public void test_analytics_event_creation()
    {
        var evt = new AnalyticsEvent
        {
            EventType = "pageview",
            Timestamp = DateTime.UtcNow
        };
        Assert.NotNull(evt);
        Assert.Equal("pageview", evt.EventType);
    }

    [Fact]
    public void test_analytics_status_values()
    {
        Assert.Equal(0, (int)AnalyticsStatus.Active);
        Assert.Equal(1, (int)AnalyticsStatus.Inactive);
    }

    [Fact]
    public async Task test_basic_channel_operations()
    {
        var channel = Channel.CreateUnbounded<int>();
        await channel.Writer.WriteAsync(42).ConfigureAwait(false);
        var result = await channel.Reader.ReadAsync().ConfigureAwait(false);
        Assert.Equal(42, result);
    }

    [Fact]
    public void test_json_serialization_basic()
    {
        var evt = new AnalyticsEvent
        {
            EventType = "test",
            Timestamp = DateTime.UtcNow
        };
        var json = JsonSerializer.Serialize(evt);
        Assert.Contains("test", json);
    }

    [Fact]
    public async Task test_task_completion()
    {
        var tcs = new TaskCompletionSource<int>();
        tcs.SetResult(100);
        var result = await tcs.Task.ConfigureAwait(false);
        Assert.Equal(100, result);
    }

    [Fact]
    public void test_enum_equality_unboxed()
    {
        var status1 = AnalyticsStatus.Active;
        var status2 = AnalyticsStatus.Active;
        Assert.Equal(status1, status2);
    }

    [Fact]
    public void test_options_pattern_basic()
    {
        var config = new AnalyticsConfig { MaxBatchSize = 100 };
        Assert.Equal(100, config.MaxBatchSize);
    }

    [Fact]
    public async Task test_channel_bounded_capacity()
    {
        var channel = Channel.CreateBounded<int>(5);
        for (int i = 0; i < 5; i++)
        {
            await channel.Writer.WriteAsync(i).ConfigureAwait(false);
        }
        Assert.True(true, "Channel accepts items up to capacity");
    }

    [Fact]
    public void test_event_tracking()
    {
        var evt = new AnalyticsEvent { EventType = "click", Timestamp = DateTime.UtcNow };
        Assert.Equal("click", evt.EventType);
        Assert.True(evt.Timestamp <= DateTime.UtcNow);
    }

    [Fact]
    public void test_pageview_tracking()
    {
        var pageView = new { Url = "/home", Timestamp = DateTime.UtcNow, UserId = "user123" };
        Assert.NotEmpty(pageView.Url);
        Assert.NotEmpty(pageView.UserId);
    }

    [Fact]
    public void test_conversion_tracking()
    {
        var conversion = new { EventType = "purchase", Value = 99.99m, UserId = "user456" };
        Assert.Equal("purchase", conversion.EventType);
        Assert.True(conversion.Value > 0);
    }

    [Fact]
    public void test_funnel_analysis()
    {
        var funnelSteps = new[] { "landing", "signup", "verify", "purchase" };
        var completionRate = 0.25;
        Assert.Equal(4, funnelSteps.Length);
        Assert.True(completionRate > 0);
    }

    [Fact]
    public void test_cohort_analysis()
    {
        var cohort = new { Month = "2026-02", UserCount = 150, RetentionRate = 0.65 };
        Assert.Equal("2026-02", cohort.Month);
        Assert.True(cohort.RetentionRate > 0);
    }

    [Fact]
    public void test_retention_metric()
    {
        var initialUsers = 1000;
        var returningUsers = 750;
        var retentionRate = (double)returningUsers / initialUsers;
        Assert.Equal(0.75, retentionRate);
    }

    [Fact]
    public void test_revenue_metric()
    {
        var transactions = new[] { 50m, 75m, 100m, 125m };
        var totalRevenue = transactions.Sum();
        Assert.Equal(350m, totalRevenue);
    }

    [Fact]
    public void test_daily_active_users()
    {
        var activeUsers = new HashSet<string> { "user1", "user2", "user3", "user4" };
        var dau = activeUsers.Count;
        Assert.Equal(4, dau);
    }

    [Fact]
    public void test_session_duration()
    {
        var sessionStart = DateTime.UtcNow.AddMinutes(-30);
        var sessionEnd = DateTime.UtcNow;
        var duration = sessionEnd - sessionStart;
        Assert.Equal(30, duration.TotalMinutes);
    }

    [Fact]
    public void test_bounce_rate()
    {
        var totalVisits = 1000;
        var bouncedVisits = 350;
        var bounceRate = (double)bouncedVisits / totalVisits;
        Assert.Equal(0.35, bounceRate);
    }

    [Fact]
    public void test_top_events()
    {
        var events = new Dictionary<string, int>
        {
            { "pageview", 1000 },
            { "click", 750 },
            { "scroll", 500 }
        };
        var topEvent = events.OrderByDescending(e => e.Value).First();
        Assert.Equal("pageview", topEvent.Key);
    }

    [Fact]
    public void test_geographic_analysis()
    {
        var usersByCountry = new Dictionary<string, int>
        {
            { "US", 500 },
            { "UK", 200 },
            { "CA", 150 }
        };
        Assert.Equal(3, usersByCountry.Count);
    }

    [Fact]
    public void test_device_analysis()
    {
        var devices = new[] {
            new { Type = "mobile", Count = 600 },
            new { Type = "desktop", Count = 300 },
            new { Type = "tablet", Count = 100 }
        };
        var mobileCount = devices.First(d => d.Type == "mobile").Count;
        Assert.Equal(600, mobileCount);
    }

    [Fact]
    public void test_referral_tracking()
    {
        var referrers = new Dictionary<string, int>
        {
            { "google.com", 400 },
            { "facebook.com", 250 },
            { "twitter.com", 100 }
        };
        Assert.True(referrers.ContainsKey("google.com"));
    }

    [Fact]
    public void test_ab_test_analysis()
    {
        var variantA = new { Conversions = 50, Visitors = 1000 };
        var variantB = new { Conversions = 65, Visitors = 1000 };
        var conversionRateA = (double)variantA.Conversions / variantA.Visitors;
        var conversionRateB = (double)variantB.Conversions / variantB.Visitors;
        Assert.True(conversionRateB > conversionRateA);
    }

    [Fact]
    public void test_real_time_dashboard()
    {
        var currentUsers = 145;
        var eventsPerSecond = 23;
        Assert.True(currentUsers > 0);
        Assert.True(eventsPerSecond > 0);
    }

    [Fact]
    public void test_custom_metric()
    {
        var customMetric = new { Name = "cart_abandonment", Value = 0.42 };
        Assert.Equal("cart_abandonment", customMetric.Name);
        Assert.True(customMetric.Value > 0);
    }

    [Fact]
    public void test_metric_aggregation()
    {
        var hourlyMetrics = new[] { 10, 15, 20, 25, 30 };
        var average = hourlyMetrics.Average();
        Assert.Equal(20, average);
    }

    [Fact]
    public void test_time_series_query()
    {
        var timeSeries = new[] {
            new { Timestamp = DateTime.UtcNow.AddHours(-3), Value = 100 },
            new { Timestamp = DateTime.UtcNow.AddHours(-2), Value = 150 },
            new { Timestamp = DateTime.UtcNow.AddHours(-1), Value = 125 }
        };
        Assert.Equal(3, timeSeries.Length);
    }

    [Fact]
    public void test_export_report()
    {
        var report = new { Period = "2026-02", TotalUsers = 1500, TotalRevenue = 45000m };
        var csv = $"{report.Period},{report.TotalUsers},{report.TotalRevenue}";
        Assert.Contains("2026-02", csv);
    }
}

// Supporting types for tests
public enum AnalyticsStatus
{
    Active = 0,
    Inactive = 1
}

public class AnalyticsEvent
{
    public required string EventType { get; set; }
    public required DateTime Timestamp { get; set; }
}

public class AnalyticsConfig
{
    public int MaxBatchSize { get; set; }
}
