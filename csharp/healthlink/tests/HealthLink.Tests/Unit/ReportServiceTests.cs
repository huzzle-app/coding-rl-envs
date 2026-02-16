using FluentAssertions;
using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Services;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace HealthLink.Tests.Unit;

public class ReportServiceTests : IDisposable
{
    private readonly HealthLinkDbContext _context;
    private readonly ReportService _service;

    public ReportServiceTests()
    {
        var options = new DbContextOptionsBuilder<HealthLinkDbContext>()
            .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
            .Options;
        _context = new HealthLinkDbContext(options);
        _service = new ReportService(_context);
    }

    [Fact]
    public async Task test_closure_capture_correct_value()
    {
        
        var start = DateTime.UtcNow.Date;
        var reports = await _service.GenerateDailyReportsAsync(start, 3);
        reports.Should().HaveCount(3);
        reports[0].Date.Should().Be(start);
        reports[1].Date.Should().Be(start.AddDays(1));
        reports[2].Date.Should().Be(start.AddDays(2));
    }

    [Fact]
    public async Task test_loop_variable_not_captured()
    {
        
        var start = DateTime.UtcNow.Date;
        var reports = await _service.GenerateDailyReportsAsync(start, 5);
        var dates = reports.Select(r => r.Date).Distinct().ToList();
        dates.Should().HaveCount(5);
    }

    [Fact]
    public void test_dbcontext_disposed_after_request()
    {
        // ReportService should not cache the DbContext in a field — it leaks across scopes
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Services", "ReportService.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        source.Should().NotContain("_cachedContext",
            "caching DbContext in a field leaks a scoped resource; use the injected _context directly");
    }

    [Fact]
    public void test_no_connection_leak()
    {
        // ReportService should not store extra references to DbContext
        var fields = typeof(ReportService).GetFields(
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        var contextFields = fields.Where(f =>
            f.FieldType == typeof(HealthLinkDbContext) || f.FieldType == typeof(HealthLinkDbContext?));
        contextFields.Should().HaveCount(1,
            "ReportService should have exactly one DbContext field; extra cached references leak scoped resources");
    }

    [Fact]
    public async Task test_daily_report_empty_days()
    {
        var start = DateTime.UtcNow.Date.AddYears(1);
        var reports = await _service.GenerateDailyReportsAsync(start, 2);
        reports.Should().AllSatisfy(r => r.AppointmentCount.Should().Be(0));
    }

    [Fact]
    public async Task test_patient_report_unknown()
    {
        var report = await _service.GeneratePatientReportAsync(99999);
        report.PatientName.Should().Be("Unknown");
    }

    public void Dispose() => _context.Dispose();
}
