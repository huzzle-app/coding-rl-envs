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
        
        var act = () => _service.OnAppointmentChanged(null, new AppointmentScheduledEventArgs { AppointmentId = 1 });
        // async void exceptions crash the process
        // After fix, should propagate correctly
    }

    [Fact]
    public async Task test_event_handler_error_propagates()
    {
        
        var eventArgs = new AppointmentScheduledEventArgs { AppointmentId = 999, PatientId = 1 };
        // The async void handler throws but exception is lost
        _service.OnAppointmentChanged(null, eventArgs);
        await Task.Delay(100); // Give async void time to complete
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
        
        await _service.SendReminderAsync(1, "Test");
        await Task.Delay(200); // Wait for fire-and-forget
        // If SMTP is not configured, exception should be logged, not lost
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

        await _service.SendAppointmentConfirmationAsync(appt.Id);
    }

    [Fact]
    public async Task test_send_confirmation_nonexistent()
    {
        await _service.SendAppointmentConfirmationAsync(99999);
    }

    public void Dispose() => _context.Dispose();
}
