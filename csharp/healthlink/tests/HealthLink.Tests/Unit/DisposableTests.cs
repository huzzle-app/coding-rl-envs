using FluentAssertions;
using HealthLink.Api.Services;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;

namespace HealthLink.Tests.Unit;

public class DisposableTests
{
    [Fact]
    public async Task test_httpclient_factory_used()
    {
        
        var logger = new Mock<ILogger<ExternalApiService>>();
        var service = new ExternalApiService(logger.Object);

        // This creates a new HttpClient per call - socket exhaustion
        var result = await service.GetInsuranceVerificationAsync("test-123");
        // After fix, should use factory
    }

    [Fact]
    public async Task test_no_socket_exhaustion()
    {
        
        var logger = new Mock<ILogger<ExternalApiService>>();
        var service = new ExternalApiService(logger.Object);

        // Making multiple calls shouldn't exhaust sockets
        for (int i = 0; i < 5; i++)
        {
            await service.GetLabResultsAsync($"order-{i}");
        }
    }

    [Fact]
    public async Task test_async_disposable_awaited()
    {
        
        var service = new ExportService();
        var data = new List<object> { "item1", "item2", "item3" };
        var result = await service.ExportToCsvAsync(data);
        result.Should().NotBeEmpty();
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
        // After disposal, writing should fail or be no-op
    }

    [Fact]
    public void test_event_handler_unsubscribed()
    {
        
        var scheduler = new SchedulingService();
        var handler = new EventHandler((s, e) => { });
        scheduler.SlotAvailable += handler;
        
        // After fix, should call scheduler.SlotAvailable -= handler in Dispose
        scheduler.SlotAvailable -= handler;
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
