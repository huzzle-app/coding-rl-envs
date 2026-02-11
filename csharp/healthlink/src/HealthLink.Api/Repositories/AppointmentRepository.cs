using HealthLink.Api.Data;
using HealthLink.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace HealthLink.Api.Repositories;

public interface IAppointmentRepository
{
    Task<List<Appointment>> GetByDateRangeAsync(DateTime start, DateTime end);
    Task<List<Appointment>> GetWithDetailsAsync(int patientId);
    Task<Appointment?> GetByIdAsync(int id);
}

public class AppointmentRepository : IAppointmentRepository
{
    private readonly HealthLinkDbContext _context;

    public AppointmentRepository(HealthLinkDbContext context)
    {
        _context = context;
    }

    public async Task<List<Appointment>> GetByDateRangeAsync(DateTime start, DateTime end)
    {
        // === BUG C2: Client-side evaluation ===
        // The custom method FormatDate() cannot be translated to SQL.
        // EF Core will pull ALL rows from the database and filter in memory.
        return await _context.Appointments
            .Where(a => FormatDate(a.DateTime) == FormatDate(start) ||
                        a.DateTime >= start && a.DateTime <= end)
            .Include(a => a.Patient)
            .ToListAsync();
    }

    public async Task<List<Appointment>> GetWithDetailsAsync(int patientId)
    {
        // === BUG E3: Include() causing cartesian explosion ===
        // Including multiple collections causes a cartesian product in SQL.
        // Should use AsSplitQuery() to split into multiple SQL queries.
        return await _context.Appointments
            .Where(a => a.PatientId == patientId)
            .Include(a => a.Patient)
                .ThenInclude(p => p.Appointments)
            .Include(a => a.Patient)
                .ThenInclude(p => p.Documents)
            .Include(a => a.Notes)
            .ToListAsync();
    }

    public async Task<Appointment?> GetByIdAsync(int id)
    {
        return await _context.Appointments
            .Include(a => a.Patient)
            .FirstOrDefaultAsync(a => a.Id == id);
    }

    private static string FormatDate(DateTime dt) => dt.ToString("yyyy-MM-dd");
}
