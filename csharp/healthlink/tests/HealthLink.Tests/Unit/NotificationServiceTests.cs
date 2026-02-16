using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Services;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Moq;
using Xunit;

namespace HealthLink.Tests.Unit;

public class NotificationServiceTests : IDisposable
{
    private readonly HealthLinkDbContext _context;
    private readonly Mock<ISchedulingService> _schedulingMock;
    private readonly NotificationService _service;

    public NotificationServiceTests()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        _context = new HealthLinkDbContext(options);
        _schedulingMock = new Mock<ISchedulingService>();
        var smtpOptions = Options.Create(new SmtpSettings { Host = "smtp.test.com", Port = 587 });
        var logger = new Mock<ILogger<NotificationService>>();
        _service = new NotificationService(_context, _schedulingMock.Object, smtpOptions, logger.Object);
    }

    [Fact]
    public async Task test_async_void_throws_handled()
    {
        // OnAppointmentChanged should return Task (not async void) so exceptions propagate
        var method = typeof(NotificationService).GetMethod("OnAppointmentChanged");
        method.Should().NotBeNull();
        method!.ReturnType.Should().Be(typeof(Task),
            "event handler should return Task, not void, so exceptions are observable");
    }

    [Fact]
    public async Task test_event_handler_error_propagates()
    {
        // Verify the method signature is async Task, not async void
        var method = typeof(NotificationService).GetMethod("OnAppointmentChanged");
        method.Should().NotBeNull();
        // async void methods have return type void; async Task methods return Task
        (method!.ReturnType == typeof(void)).Should().BeFalse(
            "async void swallows exceptions; method should return Task");
    }

    [Fact]
    public async Task test_fire_and_forget_observed()
    {
        
        var act = () => _service.SendReminderAsync(1, "Test reminder");
        await act.Should().NotThrowAsync();
    }

    [Fact]
    public async Task test_notification_errors_logged()
    {
        // SendReminderAsync should await the fire-and-forget task or observe its errors
        var method = typeof(NotificationService).GetMethod("SendReminderAsync");
        method.Should().NotBeNull();
        // Verify the method properly awaits (check source for unobserved Task.Run)
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Services", "NotificationService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // Fire-and-forget Task.Run without await is a bug; should be awaited
        var hasUnawaitedTaskRun = source.Contains("Task.Run(") && !source.Contains("await Task.Run(");
        hasUnawaitedTaskRun.Should().BeFalse(
            "Task.Run should be awaited to observe errors, not fire-and-forget");
    }

    [Fact]
    public async Task test_send_confirmation()
    {
        var patient = new Patient { Name = "Confirm", Email = "c@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();
        var appt = new Appointment { PatientId = patient.Id, DoctorId = 1, DateTime = DateTime.UtcNow };
        _context.Appointments.Add(appt);
        await _context.SaveChangesAsync();

        var act = () => _service.SendAppointmentConfirmationAsync(appt.Id);
        await act.Should().NotThrowAsync(
            "sending confirmation for existing appointment should succeed");
    }

    [Fact]
    public async Task test_send_confirmation_nonexistent()
    {
        // Sending confirmation for a non-existent appointment should not throw
        var act = () => _service.SendAppointmentConfirmationAsync(99999);
        await act.Should().NotThrowAsync(
            "sending confirmation for non-existent appointment should be handled gracefully");
    }

    public void Dispose() => _context.Dispose();
}
