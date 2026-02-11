using HealthLink.Api.Data;
using HealthLink.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace HealthLink.Api.Repositories;

public interface IPatientRepository
{
    IEnumerable<Patient> GetAll();
    Task<Patient?> GetByIdAsync(int id);
    Task<List<Patient>> SearchAsync(string searchTerm);
    Task ExecuteCustomQueryAsync(string fieldName, string value);
}

public class PatientRepository : IPatientRepository
{
    private readonly HealthLinkDbContext _context;

    public PatientRepository(HealthLinkDbContext context)
    {
        _context = context;
    }

    // === BUG C4: Returning IEnumerable instead of IQueryable ===
    // This materializes the query, preventing downstream LINQ
    // from being translated to SQL (further filtering happens in memory)
    public IEnumerable<Patient> GetAll()
    {
        return _context.Patients.ToList();
    }

    public async Task<Patient?> GetByIdAsync(int id)
    {
        return await _context.Patients.FindAsync(id);
    }

    public async Task<List<Patient>> SearchAsync(string searchTerm)
    {
        return await _context.Patients
            .Where(p => p.Name.Contains(searchTerm))
            .ToListAsync();
    }

    public async Task ExecuteCustomQueryAsync(string fieldName, string value)
    {
        // === BUG I1: SQL injection via ExecuteSqlRaw with interpolation ===
        // ExecuteSqlRaw does NOT parameterize interpolated strings
        // Should use ExecuteSqlInterpolated() instead
        await _context.Database.ExecuteSqlRawAsync(
            $"UPDATE \"Patients\" SET \"{fieldName}\" = '{value}' WHERE \"IsActive\" = true");
    }
}
