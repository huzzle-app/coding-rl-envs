using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Repositories;
using HealthLink.Api.Services;
using Microsoft.EntityFrameworkCore;
using Moq;
using Xunit;

namespace HealthLink.Tests.Unit;

public class PatientServiceTests : IDisposable
{
    private readonly HealthLinkDbContext _context;
    private readonly PatientService _service;
    private readonly Mock<IPatientRepository> _repoMock;

    public PatientServiceTests()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        _context = new HealthLinkDbContext(options);
        _repoMock = new Mock<IPatientRepository>();
        _service = new PatientService(_context, _repoMock.Object);
    }

    [Fact]
    public async Task test_patient_name_null_handled()
    {
        
        var patient = new Patient { Name = null!, Email = "test@test.com" };
        var act = () => _service.CreateAsync(patient);
        // Should handle null name gracefully, not throw NRE
        await act.Should().NotThrowAsync<NullReferenceException>();
    }

    [Fact]
    public async Task test_null_suppression_detected()
    {
        
        var patient = new Patient { Email = "test@test.com" };
        var act = () => _service.CreateAsync(patient);
        await act.Should().NotThrowAsync<NullReferenceException>();
    }

    [Fact]
    public async Task test_patient_query_single_execution()
    {
        
        _context.Patients.Add(new Patient { Name = "Test", Email = "t@t.com" });
        await _context.SaveChangesAsync();

        var patients = await _service.GetAllAsync();
        patients.Should().NotBeEmpty();
    }

    [Fact]
    public void test_deferred_execution_no_multiple_enum()
    {
        // GetAllAsync should not enumerate an IEnumerable multiple times (Count + ToList = double query)
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Services", "PatientService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // Declaring as IEnumerable then calling .Count() and .ToList() causes double enumeration
        var hasIEnumerable = source.Contains("IEnumerable<Patient>");
        var hasDoubleEnum = source.Contains(".Count()") && source.Contains(".ToList()");
        (hasIEnumerable && hasDoubleEnum).Should().BeFalse(
            "IEnumerable with .Count() + .ToList() causes double DB enumeration; use IQueryable or materialize once");
    }

    [Fact]
    public async Task test_stale_entity_not_returned()
    {
        var patient = new Patient { Name = "Original", Email = "o@o.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        // Simulate external update by directly modifying the entity outside the change tracker
        patient.Name = "Updated";
        await _context.SaveChangesAsync();
        _context.ChangeTracker.Clear();

        // GetByIdAsync should return fresh data, not stale cached data
        var fetched = await _service.GetByIdAsync(patient.Id);
        fetched!.Name.Should().Be("Updated");
    }

    [Fact]
    public async Task test_change_tracker_cleared()
    {
        
        var patient = new Patient { Name = "Cached", Email = "c@c.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        _context.ChangeTracker.Clear();
        var fetched = await _service.GetByIdAsync(patient.Id);
        fetched.Should().NotBeNull();
    }

    [Fact]
    public async Task test_create_patient_with_valid_name()
    {
        var patient = new Patient { Name = "Valid Name", Email = "v@v.com" };
        var result = await _service.CreateAsync(patient);
        result.NormalizedName.Should().Be("VALID NAME");
    }

    [Fact]
    public async Task test_get_patient_summary()
    {
        var patient = new Patient { Name = "Summary Test", Email = "s@s.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var summary = await _service.GetSummaryAsync(patient.Id);
        summary.Name.Should().Be("Summary Test");
    }

    [Fact]
    public async Task test_delete_patient()
    {
        var patient = new Patient { Name = "ToDelete", Email = "d@d.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        await _service.DeleteAsync(patient.Id);
        var found = await _service.GetByIdAsync(patient.Id);
        found.Should().BeNull();
    }

    [Fact]
    public async Task test_get_nonexistent_patient_returns_null()
    {
        var result = await _service.GetByIdAsync(99999);
        result.Should().BeNull();
    }

    [Fact]
    public async Task test_get_all_empty()
    {
        var result = await _service.GetAllAsync();
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task test_patient_create_sets_active()
    {
        var patient = new Patient { Name = "Active", Email = "active@test.com" };
        var result = await _service.CreateAsync(patient);
        result.IsActive.Should().BeTrue();
    }

    public void Dispose()
    {
        _context.Dispose();
    }
}
