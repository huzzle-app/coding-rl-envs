using HealthLink.Api.Data;
using HealthLink.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace HealthLink.Api.Services;

public interface IReportService
{
    Task<List<DailyReport>> GenerateDailyReportsAsync(DateTime startDate, int days);
    Task<PatientReport> GeneratePatientReportAsync(int patientId);
}

public class DailyReport
{
    public DateTime Date { get; set; }
    public int AppointmentCount { get; set; }
    public List<string> DoctorNames { get; set; } = new();
}

public class PatientReport
{
    public int PatientId { get; set; }
    public string PatientName { get; set; } = "";
    public int TotalAppointments { get; set; }
}

public class ReportService : IReportService
{
    // === BUG D1: DbContext used outside its scope ===
    // Storing a reference to a scoped DbContext in a field
    // that persists beyond the request scope
    private readonly HealthLinkDbContext _context;
    private HealthLinkDbContext? _cachedContext;

    public ReportService(HealthLinkDbContext context)
    {
        _context = context;
        _cachedContext = context; // Holding reference beyond scope
    }

    public async Task<List<DailyReport>> GenerateDailyReportsAsync(DateTime startDate, int days)
    {
        var reports = new List<DailyReport>();

        // === BUG C3: Closure captures loop variable by reference ===
        // The variable 'i' is captured by the lambda, not its value.
        // By the time the lambda executes, 'i' has already been incremented.
        //
        
        // When _cachedContext is used and already disposed, the DbContext throws
        // ObjectDisposedException BEFORE the closure bug manifests. Fixing D1 by
        // removing _cachedContext will REVEAL C3 - all reports will have the same date
        // (startDate + days) instead of sequential dates.
        var tasks = new List<Func<Task<DailyReport>>>();
        for (int i = 0; i < days; i++)
        {
            tasks.Add(async () =>
            {
                
                
                // AND also update GeneratePatientReportAsync to not use _cachedContext
                var date = startDate.AddDays(i);
                var count = await _context.Appointments
                    .CountAsync(a => a.DateTime.Date == date.Date);
                return new DailyReport { Date = date, AppointmentCount = count };
            });
        }

        foreach (var task in tasks)
        {
            reports.Add(await task());
        }

        return reports;
    }

    public async Task<PatientReport> GeneratePatientReportAsync(int patientId)
    {
        // Using cached context which may be disposed
        var ctx = _cachedContext ?? _context;
        var patient = await ctx.Patients.FindAsync(patientId);
        var count = await ctx.Appointments.CountAsync(a => a.PatientId == patientId);

        return new PatientReport
        {
            PatientId = patientId,
            PatientName = patient?.Name ?? "Unknown",
            TotalAppointments = count
        };
    }
}
