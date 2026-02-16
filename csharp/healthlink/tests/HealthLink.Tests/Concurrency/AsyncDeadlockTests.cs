using FluentAssertions;
using HealthLink.Api.Controllers;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Services;
using Microsoft.EntityFrameworkCore;
using Moq;
using Xunit;

namespace HealthLink.Tests.Concurrency;

public class AsyncDeadlockTests
{
    [Fact]
    public void test_no_task_result_deadlock_concurrent()
    {
        // Verify that GetAppointment doesn't block with .Result or .Wait()
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Controllers", "AppointmentController.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // .Result causes deadlocks under SynchronizationContext (ASP.NET Core, WPF, etc.)
        source.Should().NotContain(".Result",
            "using .Result on async tasks causes deadlocks under SynchronizationContext");
    }

    [Fact]
    public async Task test_concurrent_scheduling()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        var context = new HealthLinkDbContext(options);
        var notifMock = new Mock<INotificationService>();
        var service = new SchedulingService(context, notifMock.Object);

        var patient = new Patient { Name = "Concurrent", Email = "c@t.com" };
        context.Patients.Add(patient);
        await context.SaveChangesAsync();

        // Schedule multiple appointments concurrently
        var tasks = Enumerable.Range(1, 3).Select(i =>
            service.ScheduleAppointmentAsync(patient.Id, DateTime.UtcNow.AddDays(i), 1));

        var results = await Task.WhenAll(tasks);
        results.Where(r => r != null).Should().HaveCount(3);
    }

    [Fact]
    public async Task test_async_void_does_not_crash()
    {
        // OnAppointmentChanged should return Task, not be async void
        var method = typeof(NotificationService).GetMethod("OnAppointmentChanged");
        method.Should().NotBeNull();
        method!.ReturnType.Should().Be(typeof(Task),
            "async void event handlers crash the process on exception; should return Task instead");
    }

    [Fact]
    public async Task test_concurrent_cache_access()
    {
        var cacheService = new CacheService();

        // Concurrent reads and writes
        var tasks = Enumerable.Range(1, 10).Select(async i =>
        {
            await cacheService.SetAsync($"key-{i}", $"value-{i}");
            var result = await cacheService.GetAsync($"key-{i}");
            return result;
        });

        var results = await Task.WhenAll(tasks);
        results.Where(r => r != null).Should().HaveCount(10);
    }

    [Fact]
    public async Task test_valuetask_concurrent_usage()
    {
        
        var cacheService = new CacheService();
        await cacheService.SetAsync("existing", "value");

        var tasks = Enumerable.Range(1, 5).Select(i =>
            cacheService.GetOrCreateAsync($"key-{i}", () => Task.FromResult($"created-{i}")));

        var act = () => Task.WhenAll(tasks);
        await act.Should().NotThrowAsync();
    }

    [Fact]
    public async Task test_fire_and_forget_concurrent()
    {
        // Verify SendReminderAsync does not use fire-and-forget Task.Run
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Services", "NotificationService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // Unawaited Task.Run is a fire-and-forget that loses exceptions
        var hasUnawaitedTaskRun = source.Contains("Task.Run(") && !source.Contains("await Task.Run(");
        hasUnawaitedTaskRun.Should().BeFalse(
            "Task.Run should be awaited; fire-and-forget loses exceptions silently");
    }

    [Fact]
    public async Task test_concurrent_patient_creation()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        var context = new HealthLinkDbContext(options);
        var repoMock = new Mock<HealthLink.Api.Repositories.IPatientRepository>();
        var service = new PatientService(context, repoMock.Object);

        var tasks = Enumerable.Range(1, 5).Select(i =>
            service.CreateAsync(new Patient { Name = $"Patient-{i}", Email = $"p{i}@t.com" }));

        var results = await Task.WhenAll(tasks);
        results.Should().HaveCount(5);
    }

    [Fact]
    public async Task test_concurrent_report_generation()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        var context = new HealthLinkDbContext(options);
        var service = new ReportService(context);

        var tasks = Enumerable.Range(1, 3).Select(i =>
            service.GenerateDailyReportsAsync(DateTime.UtcNow.Date.AddDays(i * 10), 2));

        var results = await Task.WhenAll(tasks);
        results.Should().HaveCount(3);
    }

    [Fact]
    public async Task test_event_subscription_thread_safe()
    {
        
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        var context = new HealthLinkDbContext(options);
        var notifMock = new Mock<INotificationService>();
        var service = new SchedulingService(context, notifMock.Object);

        int count = 0;
        service.AppointmentScheduled += (s, e) => Interlocked.Increment(ref count);
        service.AppointmentScheduled += (s, e) => Interlocked.Increment(ref count);

        var patient = new Patient { Name = "Sub", Email = "sub@t.com" };
        context.Patients.Add(patient);
        await context.SaveChangesAsync();

        await service.ScheduleAppointmentAsync(patient.Id, DateTime.UtcNow.AddDays(20), 1);
        count.Should().Be(2);
    }

    [Fact]
    public async Task test_concurrent_export()
    {
        var service = new ExportService();
        var tasks = Enumerable.Range(1, 5).Select(i =>
        {
            var data = Enumerable.Range(1, 10).Select(j => (object)$"item-{i}-{j}").ToList();
            return service.ExportToCsvAsync(data);
        });

        var results = await Task.WhenAll(tasks);
        results.Should().AllSatisfy(r => r.Should().NotBeEmpty());
    }
}
