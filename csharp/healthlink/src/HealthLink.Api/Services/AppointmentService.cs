using HealthLink.Api.Data;
using HealthLink.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace HealthLink.Api.Services;

public interface IAppointmentService
{
    Task<Appointment?> GetByIdAsync(int id);
    Task<List<Appointment>> GetAllAsync();
    Task<Appointment> CreateAsync(Appointment appointment);
    Task<List<Appointment>> GetByStatusAsync(AppointmentStatus status);
}

public class AppointmentService : IAppointmentService
{
    private readonly HealthLinkDbContext _context;

    public AppointmentService(HealthLinkDbContext context)
    {
        _context = context;
    }

    public async Task<Appointment?> GetByIdAsync(int id)
    {
        return await _context.Appointments
            .Include(a => a.Patient)
            .FirstOrDefaultAsync(a => a.Id == id);
    }

    public async Task<List<Appointment>> GetAllAsync()
    {
        return await _context.Appointments
            .Include(a => a.Patient)
            .ToListAsync();
    }

    public async Task<Appointment> CreateAsync(Appointment appointment)
    {
        _context.Appointments.Add(appointment);
        await _context.SaveChangesAsync();
        return appointment;
    }

    public async Task<List<Appointment>> GetByStatusAsync(AppointmentStatus status)
    {
        // === BUG B4: Boxed enum equality ===
        // Casting status to object and using Equals() on boxed enums
        // can produce unexpected results due to boxing behavior
        var allAppointments = await _context.Appointments.ToListAsync();

        return allAppointments.Where(a =>
        {
            object boxedStatus = a.Status;
            object boxedFilter = status;
            return boxedStatus.Equals((int)boxedFilter); // Comparing boxed enum to boxed int fails
        }).ToList();
    }
}
