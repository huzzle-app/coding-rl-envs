using FluentAssertions;
using HealthLink.Api.Services;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace HealthLink.Tests.Unit;

public class DisposableTests
{
    [Fact]
    public void test_httpclient_factory_used()
    {
        // ExternalApiService should accept IHttpClientFactory, not create HttpClient directly
        var ctors = typeof(ExternalApiService).GetConstructors();
        var hasFactoryParam = ctors.Any(c =>
            c.GetParameters().Any(p => p.ParameterType == typeof(IHttpClientFactory)));
        hasFactoryParam.Should().BeTrue(
            "ExternalApiService should accept IHttpClientFactory to avoid socket exhaustion");
    }

    [Fact]
    public void test_no_socket_exhaustion()
    {
        // Verify that ExternalApiService does not directly instantiate HttpClient
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Services", "ExternalApiService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        source.Should().NotContain("new HttpClient()",
            "should use IHttpClientFactory instead of new HttpClient()");
    }

    [Fact]
    public void test_async_disposable_awaited()
    {
        // ExportService should use 'await using' for IAsyncDisposable resources
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Services", "ExportService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        source.Should().Contain("await using",
            "CsvWriter implements IAsyncDisposable; must use 'await using' not 'using'");
    }

    [Fact]
    public async Task test_export_stream_closed()
    {
        
        var service = new ExportService();
        var data = new List<object> { "row1", "row2" };
        var bytes = await service.ExportToCsvAsync(data);
        var csv = System.Text.Encoding.UTF8.GetString(bytes);
        csv.Should().Contain("Id,Name,Value");
        csv.Should().Contain("row1");
    }

    [Fact]
    public async Task test_export_empty_data()
    {
        var service = new ExportService();
        var result = await service.ExportToCsvAsync(new List<object>());
        result.Should().NotBeEmpty();
    }

    [Fact]
    public async Task test_export_large_data()
    {
        var service = new ExportService();
        var data = Enumerable.Range(1, 100).Select(i => (object)$"item-{i}").ToList();
        var result = await service.ExportToCsvAsync(data);
        result.Should().NotBeEmpty();
    }

    [Fact]
    public async Task test_csv_writer_disposes()
    {
        var stream = new MemoryStream();
        var writer = new CsvWriter(stream);
        await writer.WriteLineAsync("test");
        await writer.DisposeAsync();
        // After disposal, stream should have been flushed with content
        stream.ToArray().Length.Should().BeGreaterThan(0,
            "CsvWriter should flush content to stream before disposal");
    }

    [Fact]
    public void test_event_handler_unsubscribed()
    {
        // SchedulingService should implement IDisposable to clean up event subscriptions
        typeof(SchedulingService).GetInterfaces()
            .Should().Contain(typeof(IDisposable),
                "SchedulingService should implement IDisposable to unsubscribe event handlers");
    }

    [Fact]
    public void test_no_event_handler_leak()
    {
        
        var scheduler = new SchedulingService();
        var subscriberCount = 0;

        for (int i = 0; i < 10; i++)
        {
            scheduler.SlotAvailable += (s, e) => subscriberCount++;
            
        }

        // After fix, old handlers should be cleaned up
        scheduler.NotifySlotAvailable();
        subscriberCount.Should().BeLessOrEqualTo(1, "Event handlers should not accumulate");
    }
}
