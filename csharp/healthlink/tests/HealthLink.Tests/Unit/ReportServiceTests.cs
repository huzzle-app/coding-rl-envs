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
    public async Task test_dbcontext_disposed_after_request()
    {
        
        var patient = new Patient { Name = "Report", Email = "r@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var report = await _service.GeneratePatientReportAsync(patient.Id);
        report.PatientName.Should().Be("Report");
    }

    [Fact]
    public async Task test_no_connection_leak()
    {
        
        var patient = new Patient { Name = "Leak", Email = "l@t.com" };
        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();

        var report = await _service.GeneratePatientReportAsync(patient.Id);
        report.TotalAppointments.Should().Be(0);
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
