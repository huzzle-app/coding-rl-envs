namespace HealthLink.Api.Models;

// === BUG B3: default(TimeSlot) creates zero-value struct ===
// For value types, default() initializes all fields to zero/null/false.
// A TimeSlot with StartHour=0, EndHour=0 is technically valid but meaningless.
// Code that doesn't check for default values may treat 00:00-00:00 as a real slot.

public struct TimeSlot
{
    public int StartHour { get; set; }
    public int EndHour { get; set; }

    public bool IsValid => StartHour >= 0 && EndHour > StartHour && StartHour < 24 && EndHour <= 24;

    
    // IsValid returns false for default, but code often doesn't check
    public TimeSpan Duration => TimeSpan.FromHours(EndHour - StartHour);
}

public class Appointment
{
    public int Id { get; set; }
    public int PatientId { get; set; }
    public int DoctorId { get; set; }
    public DateTime DateTime { get; set; }
    public AppointmentStatus Status { get; set; }
    public TimeSlot Slot { get; set; } // default(TimeSlot) = zero values!

    public Patient Patient { get; set; } = null!;
    public List<AppointmentNote> Notes { get; set; } = new();
}

public class AppointmentNote
{
    public int Id { get; set; }
    public int AppointmentId { get; set; }
    public string Content { get; set; } = "";
    public DateTime CreatedAt { get; set; }

    public Appointment Appointment { get; set; } = null!;
}

public enum AppointmentStatus
{
    Scheduled = 0,
    Confirmed = 1,
    InProgress = 2,
    Completed = 3,
    Cancelled = 4,
    NoShow = 5
}
