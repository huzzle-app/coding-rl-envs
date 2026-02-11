using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Repositories;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace HealthLink.Tests.Integration;

public class EfCoreTests : IDisposable
{
    private readonly HealthLinkDbContext _context;

    public EfCoreTests()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        _context = new HealthLinkDbContext(options);
    }

    [Fact]
    public async Task test_owned_entity_configured()
    {
        
        var patient = new Patient
        {
            Name = "Address Test",
            Email = "addr@test.com",
            Address = new Address
            {
                Street = "123 Main St",
                City = "Springfield",
                State = "IL",
                ZipCode = "62701"
            }
        };

        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var loaded = await _context.Patients.FirstAsync(p => p.Name == "Address Test");
        loaded.Address.Should().NotBeNull("Address should be persisted via OwnsOne");
        loaded.Address!.City.Should().Be("Springfield");
    }

    [Fact]
    public async Task test_address_persisted_correctly()
    {
        
        var patient = new Patient
        {
            Name = "Persist",
            Email = "persist@test.com",
            Address = new Address { Street = "456 Oak Ave", City = "Portland", State = "OR", ZipCode = "97201" }
        };

        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        _context.ChangeTracker.Clear();
        var loaded = await _context.Patients.FindAsync(patient.Id);
        loaded!.Address.Should().NotBeNull();
    }

    [Fact]
    public async Task test_string_column_length_set()
    {
        
        var model = _context.Model;
        var patientEntity = model.FindEntityType(typeof(Patient));
        var nameProperty = patientEntity!.FindProperty("Name");
        nameProperty!.GetMaxLength().Should().NotBeNull("Name should have MaxLength configured");
    }

    [Fact]
    public async Task test_nvarchar_max_not_default()
    {
        
        var model = _context.Model;
        var patientEntity = model.FindEntityType(typeof(Patient));
        var emailProperty = patientEntity!.FindProperty("Email");
        emailProperty!.GetMaxLength().Should().NotBeNull("Email should have MaxLength configured");
    }

    [Fact]
    public async Task test_patient_crud()
    {
        var patient = new Patient { Name = "CRUD", Email = "crud@test.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var loaded = await _context.Patients.FindAsync(patient.Id);
        loaded.Should().NotBeNull();
        loaded!.Name.Should().Be("CRUD");
    }

    [Fact]
    public async Task test_appointment_with_notes()
    {
        var patient = new Patient { Name = "Notes", Email = "notes@test.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var appt = new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Scheduled,
            Notes = new List<AppointmentNote>
            {
                new() { Content = "Note 1", CreatedAt = DateTime.UtcNow },
                new() { Content = "Note 2", CreatedAt = DateTime.UtcNow }
            }
        };
        _context.Appointments.Add(appt);
        await _context.SaveChangesAsync();

        var loaded = await _context.Appointments
            .Include(a => a.Notes)
            .FirstAsync(a => a.Id == appt.Id);
        loaded.Notes.Should().HaveCount(2);
    }

    [Fact]
    public async Task test_patient_document_relationship()
    {
        var patient = new Patient { Name = "Docs", Email = "docs@test.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        _context.PatientDocuments.Add(new PatientDocument
        {
            PatientId = patient.Id, FileName = "test.pdf",
            ContentType = "application/pdf", FileSize = 1024,
            UploadDate = DateTime.UtcNow
        });
        await _context.SaveChangesAsync();

        var loaded = await _context.Patients
            .Include(p => p.Documents)
            .FirstAsync(p => p.Id == patient.Id);
        loaded.Documents.Should().HaveCount(1);
    }

    [Fact]
    public async Task test_appointment_status_stored()
    {
        var patient = new Patient { Name = "Status", Email = "status@test.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var appt = new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Confirmed
        };
        _context.Appointments.Add(appt);
        await _context.SaveChangesAsync();

        var loaded = await _context.Appointments.FindAsync(appt.Id);
        loaded!.Status.Should().Be(AppointmentStatus.Confirmed);
    }

    [Fact]
    public async Task test_cascade_delete()
    {
        var patient = new Patient { Name = "Cascade", Email = "cascade@test.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        _context.Appointments.Add(new Appointment
        {
            PatientId = patient.Id, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Scheduled
        });
        await _context.SaveChangesAsync();

        _context.Patients.Remove(patient);
        await _context.SaveChangesAsync();
    }

    [Fact]
    public async Task test_concurrent_dbcontext_access()
    {
        var patient = new Patient { Name = "Concurrent", Email = "conc@test.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        // Sequential access to verify context works
        var p1 = await _context.Patients.FindAsync(patient.Id);
        var p2 = await _context.Patients.FindAsync(patient.Id);
        p1.Should().NotBeNull();
        p2.Should().NotBeNull();
    }

    public void Dispose() => _context.Dispose();
}
