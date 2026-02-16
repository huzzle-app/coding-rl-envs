using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Services;
using Microsoft.EntityFrameworkCore;
using Moq;
using Xunit;

namespace HealthLink.Tests.Unit;

public class SchedulingServiceTests : IDisposable
{
    private readonly HealthLinkDbContext _context;
    private readonly Mock<INotificationService> _notificationMock;
    private readonly SchedulingService _service;

    public SchedulingServiceTests()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        _context = new HealthLinkDbContext(options);
        _notificationMock = new Mock<INotificationService>();
        _service = new SchedulingService(_context, _notificationMock.Object);
    }

    [Fact]
    public void test_configure_await_false_in_library()
    {
        // Library code should use ConfigureAwait(false) on await calls to prevent deadlocks
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Services", "SchedulingService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        var configureAwaitCount = System.Text.RegularExpressions.Regex.Matches(source, @"ConfigureAwait\(false\)").Count;
        configureAwaitCount.Should().BeGreaterOrEqualTo(2,
            "library code should use ConfigureAwait(false) on await calls to prevent deadlocks when called with .Result");
    }

    [Fact]
    public async Task test_no_synchronization_context_deadlock()
    {
        var patient = new Patient { Name = "Sync", Email = "s@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var act = () => _service.ScheduleAppointmentAsync(patient.Id, DateTime.UtcNow.AddDays(2), 1);
        await act.Should().CompleteWithinAsync(TimeSpan.FromSeconds(5));
    }

    [Fact]
    public async Task test_schedule_prevents_double_booking()
    {
        var patient = new Patient { Name = "Double", Email = "d@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var dt = DateTime.UtcNow.AddDays(3);
        await _service.ScheduleAppointmentAsync(patient.Id, dt, 1);
        var second = await _service.ScheduleAppointmentAsync(patient.Id, dt, 1);
        second.Should().BeNull();
    }

    [Fact]
    public async Task test_get_available_slots()
    {
        var slots = await _service.GetAvailableSlotsAsync(1, DateTime.UtcNow.AddDays(1));
        slots.Should().HaveCount(8); // 9 AM to 5 PM
    }

    [Fact]
    public async Task test_available_slots_excludes_booked()
    {
        var patient = new Patient { Name = "Booked", Email = "b@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var date = DateTime.UtcNow.Date.AddDays(5);
        _context.Appointments.Add(new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = date.AddHours(10), Status = AppointmentStatus.Scheduled
        });
        await _context.SaveChangesAsync();

        var slots = await _service.GetAvailableSlotsAsync(1, date);
        slots.Should().HaveCount(7);
    }

    [Fact]
    public async Task test_schedule_raises_event()
    {
        var patient = new Patient { Name = "Event", Email = "e@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var eventRaised = false;
        _service.AppointmentScheduled += (s, e) => eventRaised = true;
        await _service.ScheduleAppointmentAsync(patient.Id, DateTime.UtcNow.AddDays(4), 1);
        eventRaised.Should().BeTrue();
    }

    public void Dispose() => _context.Dispose();
}
