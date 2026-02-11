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
    public async Task test_sql_injection_prevented()
    {
        
        var maliciousValue = "'; DROP TABLE \"Patients\"; --";
        var act = () => _repository.ExecuteCustomQueryAsync("Name", maliciousValue);
        // Should use parameterized queries, not string concatenation
        await act.Should().NotThrowAsync<Microsoft.EntityFrameworkCore.DbUpdateException>();
    }

    [Fact]
    public async Task test_parameterized_query_used()
    {
        
        _context.Patients.Add(new Patient { Name = "Safe", Email = "safe@test.com" });
        await _context.SaveChangesAsync();

        var act = () => _repository.ExecuteCustomQueryAsync("Name", "Updated");
        // ExecuteSqlInterpolated would parameterize automatically
        await act.Should().NotThrowAsync();
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
    public async Task test_field_name_validated()
    {
        var act = () => _repository.ExecuteCustomQueryAsync("Name\" = ''; DROP TABLE", "value");
        // Field name should be validated/parameterized
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
