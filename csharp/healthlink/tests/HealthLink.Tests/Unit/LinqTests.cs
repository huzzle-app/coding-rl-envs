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
    public void test_no_client_side_evaluation()
    {
        // GetByDateRangeAsync should not use custom C# methods in LINQ-to-SQL expressions
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Repositories", "AppointmentRepository.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        source.Should().NotContain("FormatDate(",
            "FormatDate is a C# method that cannot be translated to SQL; use DateTime comparison directly");
    }

    [Fact]
    public void test_query_translates_to_sql()
    {
        // Verify that the query in GetByDateRangeAsync uses only SQL-translatable expressions
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Repositories", "AppointmentRepository.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // The Where clause should not call any private helper methods
        var hasCustomMethodInWhere = source.Contains(".Where(a => FormatDate(");
        hasCustomMethodInWhere.Should().BeFalse(
            "LINQ Where clauses must use only expressions translatable to SQL");
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
    public void test_repository_returns_queryable()
    {
        // GetAll should return IQueryable, not IEnumerable, to allow DB-level filtering
        var method = typeof(PatientRepository).GetMethod("GetAll");
        method.Should().NotBeNull();
        var returnType = method!.ReturnType;
        // Should return IQueryable<Patient> to enable further server-side filtering
        returnType.Should().BeAssignableTo(typeof(IQueryable<Patient>),
            "GetAll should return IQueryable to allow DB-level filtering, not IEnumerable");
    }

    [Fact]
    public void test_include_no_cartesian_explosion()
    {
        // GetWithDetailsAsync should use AsSplitQuery to avoid cartesian explosion
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Repositories", "AppointmentRepository.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        source.Should().Contain("AsSplitQuery",
            "queries with multiple Include() calls should use AsSplitQuery() to avoid cartesian explosion");
    }

    [Fact]
    public async Task test_split_query_used()
    {
        var repo = new AppointmentRepository(_context);
        var patient = new Patient { Name = "Split", Email = "split@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var result = await repo.GetWithDetailsAsync(patient.Id);
        result.Should().BeEmpty();
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
