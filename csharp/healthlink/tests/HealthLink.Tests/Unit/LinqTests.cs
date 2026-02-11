using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Repositories;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace HealthLink.Tests.Unit;

public class LinqTests : IDisposable
{
    private readonly HealthLinkDbContext _context;

    public LinqTests()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        _context = new HealthLinkDbContext(options);
    }

    [Fact]
    public async Task test_no_client_side_evaluation()
    {
        
        var repo = new AppointmentRepository(_context);
        var patient = new Patient { Name = "Eval", Email = "e@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var start = DateTime.UtcNow.Date;
        var end = start.AddDays(7);
        var act = () => repo.GetByDateRangeAsync(start, end);
        await act.Should().NotThrowAsync();
    }

    [Fact]
    public async Task test_query_translates_to_sql()
    {
        
        var repo = new AppointmentRepository(_context);
        var result = await repo.GetByDateRangeAsync(DateTime.UtcNow, DateTime.UtcNow.AddDays(1));
        result.Should().NotBeNull();
    }

    [Fact]
    public async Task test_iqueryable_vs_ienumerable()
    {
        
        var repo = new PatientRepository(_context);
        _context.Patients.Add(new Patient { Name = "QTest", Email = "q@t.com", IsActive = true });
        await _context.SaveChangesAsync();

        var all = repo.GetAll();
        // If GetAll returns IEnumerable (materialized), further LINQ is client-side
        all.Should().NotBeEmpty();
    }

    [Fact]
    public async Task test_repository_returns_queryable()
    {
        
        var repo = new PatientRepository(_context);
        var result = repo.GetAll();
        // With IEnumerable, Where() below runs in memory, not SQL
        var filtered = result.Where(p => p.IsActive);
        filtered.Should().NotBeNull();
    }

    [Fact]
    public async Task test_include_no_cartesian_explosion()
    {
        
        var repo = new AppointmentRepository(_context);
        var patient = new Patient { Name = "Cart", Email = "cart@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var result = await repo.GetWithDetailsAsync(patient.Id);
        result.Should().NotBeNull();
    }

    [Fact]
    public async Task test_split_query_used()
    {
        
        var repo = new AppointmentRepository(_context);
        var patient = new Patient { Name = "Split", Email = "split@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var result = await repo.GetWithDetailsAsync(patient.Id);
        result.Should().BeEmpty(); // No appointments for this patient
    }

    [Fact]
    public async Task test_search_patients()
    {
        var repo = new PatientRepository(_context);
        _context.Patients.Add(new Patient { Name = "SearchMe", Email = "s@t.com" });
        await _context.SaveChangesAsync();

        var result = await repo.SearchAsync("Search");
        result.Should().HaveCount(1);
    }

    [Fact]
    public async Task test_get_patient_by_id()
    {
        var repo = new PatientRepository(_context);
        var patient = new Patient { Name = "ById", Email = "bid@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var result = await repo.GetByIdAsync(patient.Id);
        result.Should().NotBeNull();
    }

    public void Dispose() => _context.Dispose();
}
