using HealthLink.Api.Data;
using HealthLink.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace HealthLink.Api.Services;

public interface ISchedulingService
{
    Task<Appointment?> ScheduleAppointmentAsync(int patientId, DateTime dateTime, int doctorId);
    Task<List<TimeSlot>> GetAvailableSlotsAsync(int doctorId, DateTime date);
    event EventHandler<AppointmentScheduledEventArgs>? AppointmentScheduled;
}

public class AppointmentScheduledEventArgs : EventArgs
{
    public int AppointmentId { get; set; }
    public int PatientId { get; set; }
}

public class SchedulingService : ISchedulingService
{
    private readonly HealthLinkDbContext _context;
    private readonly INotificationService _notificationService;

    public event EventHandler<AppointmentScheduledEventArgs>? AppointmentScheduled;

    public event EventHandler? SlotAvailable;

    public SchedulingService(
        HealthLinkDbContext context,
        INotificationService notificationService)
    {
        _context = context;
        _notificationService = notificationService;
    }

    public SchedulingService()
    {
        _context = null!;
        _notificationService = null!;
    }

    
    public void NotifySlotAvailable()
    {
        SlotAvailable?.Invoke(this, EventArgs.Empty);
    }

    public async Task<Appointment?> ScheduleAppointmentAsync(int patientId, DateTime dateTime, int doctorId)
    {
        var existing = await _context.Appointments
            .AnyAsync(a => a.DoctorId == doctorId && a.DateTime == dateTime);

        if (existing)
            return null;

        var appointment = new Appointment
        {
            PatientId = patientId,
            DateTime = dateTime,
            DoctorId = doctorId,
            Status = AppointmentStatus.Scheduled
        };

        _context.Appointments.Add(appointment);
        await _context.SaveChangesAsync();

        // Notify
        await _notificationService.SendAppointmentConfirmationAsync(appointment.Id);

        // Raise event
        AppointmentScheduled?.Invoke(this, new AppointmentScheduledEventArgs
        {
            AppointmentId = appointment.Id,
            PatientId = patientId
        });

        return appointment;
    }

    public async Task<List<TimeSlot>> GetAvailableSlotsAsync(int doctorId, DateTime date)
    {
        var bookedSlots = await _context.Appointments
            .Where(a => a.DoctorId == doctorId && a.DateTime.Date == date.Date)
            .Select(a => a.DateTime.Hour)
            .ToListAsync();

        var availableSlots = new List<TimeSlot>();
        for (int hour = 9; hour < 17; hour++)
        {
            if (!bookedSlots.Contains(hour))
            {
                availableSlots.Add(new TimeSlot { StartHour = hour, EndHour = hour + 1 });
            }
        }

        return availableSlots;
    }
}
