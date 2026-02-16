using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Repositories;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace HealthLink.Tests.Security;

public class SqlInjectionTests : IDisposable
{
    private readonly HealthLinkDbContext _context;
    private readonly PatientRepository _repository;

    public SqlInjectionTests()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        _context = new HealthLinkDbContext(options);
        _repository = new PatientRepository(_context);
    }

    [Fact]
    public void test_sql_injection_prevented()
    {
        // Verify that ExecuteCustomQueryAsync uses parameterized queries
        // by checking source code doesn't use ExecuteSqlRawAsync with interpolation
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Repositories", "PatientRepository.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        source.Should().NotContain("ExecuteSqlRawAsync($",
            "should use ExecuteSqlInterpolatedAsync instead of ExecuteSqlRawAsync with interpolation");
    }

    [Fact]
    public void test_parameterized_query_used()
    {
        // Verify the repository uses ExecuteSqlInterpolated or parameterized queries
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Repositories", "PatientRepository.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // Should use ExecuteSqlInterpolatedAsync or FormattableString-based methods
        var usesInterpolated = source.Contains("ExecuteSqlInterpolatedAsync") ||
                              source.Contains("ExecuteSqlAsync") ||
                              (source.Contains("ExecuteSqlRawAsync") && source.Contains("{0}"));
        usesInterpolated.Should().BeTrue(
            "should use parameterized queries to prevent SQL injection");
    }

    [Fact]
    public async Task test_search_parameterized()
    {
        _context.Patients.Add(new Patient { Name = "Search Test", Email = "st@test.com" });
        await _context.SaveChangesAsync();

        var result = await _repository.SearchAsync("' OR 1=1 --");
        result.Should().BeEmpty();
    }

    [Fact]
    public void test_field_name_validated()
    {
        // Verify that ExecuteCustomQueryAsync does not use raw string interpolation
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Repositories", "PatientRepository.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // Field names should not be directly interpolated into SQL strings
        var hasRawInterpolation = source.Contains("$\"") && source.Contains("ExecuteSqlRaw");
        hasRawInterpolation.Should().BeFalse(
            "field names and values should be parameterized, not interpolated into raw SQL");
    }

    [Fact]
    public async Task test_special_characters_escaped()
    {
        _context.Patients.Add(new Patient { Name = "O'Brien", Email = "ob@test.com" });
        await _context.SaveChangesAsync();

        var result = await _repository.SearchAsync("O'Brien");
        result.Should().HaveCount(1);
    }

    public void Dispose() => _context.Dispose();
}
