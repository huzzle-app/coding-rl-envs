using HealthLink.Api.Data;
using HealthLink.Api.Models;
using HealthLink.Api.Repositories;
using Microsoft.EntityFrameworkCore;

namespace HealthLink.Api.Services;

public interface IPatientService
{
    Task<Patient?> GetByIdAsync(int id);
    Task<List<Patient>> GetAllAsync();
    Task<Patient> CreateAsync(Patient patient);
    Task DeleteAsync(int id);
    Task UpdateSensitiveDataAsync(int id, object data);
    Task<PatientSummary> GetSummaryAsync(int id);
}

public class PatientService : IPatientService
{
    private readonly HealthLinkDbContext _context;
    private readonly IPatientRepository _patientRepository;

    public PatientService(HealthLinkDbContext context, IPatientRepository patientRepository)
    {
        _context = context;
        _patientRepository = patientRepository;
    }

    public async Task<Patient?> GetByIdAsync(int id)
    {
        return await _context.Patients.FindAsync(id);
    }

    public async Task<List<Patient>> GetAllAsync()
    {
        IEnumerable<Patient> activePatients = _context.Patients
            .Where(p => p.IsActive);

        var count = activePatients.Count(); // First DB query
        Console.WriteLine($"Found {count} active patients");

        var result = activePatients.ToList(); // Second DB query - hits DB again!
        return result;
    }

    public async Task<Patient> CreateAsync(Patient patient)
    {
        var normalizedName = patient.Name.ToUpper();
        patient.NormalizedName = normalizedName;

        _context.Patients.Add(patient);
        await _context.SaveChangesAsync();
        return patient;
    }

    public async Task DeleteAsync(int id)
    {
        var patient = await _context.Patients.FindAsync(id);
        if (patient != null)
        {
            _context.Patients.Remove(patient);
            await _context.SaveChangesAsync();
        }
    }

    public async Task UpdateSensitiveDataAsync(int id, object data)
    {
        var patient = await _context.Patients.FindAsync(id);
        if (patient != null)
        {
            // Update implementation
            await _context.SaveChangesAsync();
        }
    }

    public async Task<PatientSummary> GetSummaryAsync(int id)
    {
        var patient = await GetByIdAsync(id);
        return new PatientSummary
        {
            Id = patient?.Id ?? 0,
            Name = patient?.Name ?? "Unknown",
            AppointmentCount = patient?.Appointments?.Count ?? 0
        };
    }
}

public class PatientSummary
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public int AppointmentCount { get; set; }
}
