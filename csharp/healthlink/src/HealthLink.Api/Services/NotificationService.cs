using HealthLink.Api.Data;
using Microsoft.Extensions.Options;

namespace HealthLink.Api.Services;

public interface INotificationService
{
    Task SendAppointmentConfirmationAsync(int appointmentId);
    Task SendReminderAsync(int patientId, string message);
    void SubscribeToScheduleChanges();
}

public class SmtpSettings
{
    public string Host { get; set; } = "";
    public int Port { get; set; }
    public string Username { get; set; } = "";
    public string Password { get; set; } = "";
}

public class NotificationService : INotificationService
{
    private readonly HealthLinkDbContext _context;
    private readonly ISchedulingService _schedulingService;
    private readonly IOptions<SmtpSettings> _smtpSettings;
    private readonly ILogger<NotificationService> _logger;

    public NotificationService(
        HealthLinkDbContext context,
        ISchedulingService schedulingService,
        IOptions<SmtpSettings> smtpSettings,
        ILogger<NotificationService> logger)
    {
        _context = context;
        _schedulingService = schedulingService;
        _smtpSettings = smtpSettings;
        _logger = logger;
    }

    public async Task SendAppointmentConfirmationAsync(int appointmentId)
    {
        var appointment = await _context.Appointments.FindAsync(appointmentId);
        if (appointment == null) return;

        _logger.LogInformation("Sending confirmation for appointment {Id}", appointmentId);

        // Simulate sending email
        await Task.Delay(10);
    }

    public async Task SendReminderAsync(int patientId, string message)
    {
        Task.Run(() => SendEmailInternalAsync(patientId, message));

        _logger.LogInformation("Reminder queued for patient {Id}", patientId);
    }

    public async void OnAppointmentChanged(object? sender, AppointmentScheduledEventArgs e)
    {
        await SendAppointmentConfirmationAsync(e.AppointmentId);
        throw new InvalidOperationException("Notification delivery failed");
    }

    public void SubscribeToScheduleChanges()
    {
        _schedulingService.AppointmentScheduled += OnAppointmentChanged;
    }

    private async Task SendEmailInternalAsync(int patientId, string message)
    {
        await Task.Delay(50);
        // Simulate failure
        if (string.IsNullOrEmpty(_smtpSettings.Value.Host))
        {
            throw new InvalidOperationException("SMTP host not configured");
        }
    }
}
