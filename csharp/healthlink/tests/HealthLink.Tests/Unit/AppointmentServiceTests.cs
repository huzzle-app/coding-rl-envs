using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Services;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace HealthLink.Tests.Unit;

public class AppointmentServiceTests : IDisposable
{
    private readonly HealthLinkDbContext _context;
    private readonly AppointmentService _service;

    public AppointmentServiceTests()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        _context = new HealthLinkDbContext(options);
        _service = new AppointmentService(_context);
    }

    [Fact]
    public async Task test_status_comparison_correct()
    {
        
        var patient = new Patient { Name = "Test", Email = "t@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var appt = new Appointment
        {
            PatientId = patient.Id,
            DoctorId = 1,
            DateTime = DateTime.UtcNow,
            Status = AppointmentStatus.Scheduled
        };
        _context.Appointments.Add(appt);
        await _context.SaveChangesAsync();

        var result = await _service.GetByStatusAsync(AppointmentStatus.Scheduled);
        result.Should().HaveCount(1);
    }

    [Fact]
    public async Task test_boxed_enum_equality()
    {
        
        var patient = new Patient { Name = "Test2", Email = "t2@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        _context.Appointments.Add(new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Confirmed
        });
        _context.Appointments.Add(new Appointment
        {
            PatientId = patient.Id, DoctorId = 2,
            DateTime = DateTime.UtcNow.AddHours(1), Status = AppointmentStatus.Scheduled
        });
        await _context.SaveChangesAsync();

        var confirmed = await _service.GetByStatusAsync(AppointmentStatus.Confirmed);
        confirmed.Should().HaveCount(1);
    }

    [Fact]
    public async Task test_get_appointment_by_id()
    {
        var patient = new Patient { Name = "ById", Email = "by@id.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var appt = new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Scheduled
        };
        _context.Appointments.Add(appt);
        await _context.SaveChangesAsync();

        var result = await _service.GetByIdAsync(appt.Id);
        result.Should().NotBeNull();
    }

    [Fact]
    public async Task test_get_all_appointments()
    {
        var result = await _service.GetAllAsync();
        result.Should().NotBeNull();
    }

    [Fact]
    public async Task test_create_appointment()
    {
        var patient = new Patient { Name = "Create", Email = "cr@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var appt = new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Scheduled
        };
        var result = await _service.CreateAsync(appt);
        result.Id.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task test_get_nonexistent_appointment()
    {
        var result = await _service.GetByIdAsync(99999);
        result.Should().BeNull();
    }

    [Fact]
    public async Task test_filter_by_cancelled_status()
    {
        var patient = new Patient { Name = "Cancel", Email = "c@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        _context.Appointments.Add(new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Cancelled
        });
        await _context.SaveChangesAsync();

        var result = await _service.GetByStatusAsync(AppointmentStatus.Cancelled);
        result.Should().HaveCount(1);
    }

    [Fact]
    public async Task test_appointment_includes_patient()
    {
        var patient = new Patient { Name = "Include", Email = "inc@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var appt = new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Scheduled
        };
        _context.Appointments.Add(appt);
        await _context.SaveChangesAsync();

        var result = await _service.GetByIdAsync(appt.Id);
        result!.Patient.Should().NotBeNull();
    }

    public void Dispose()
    {
        _context.Dispose();
    }
}
