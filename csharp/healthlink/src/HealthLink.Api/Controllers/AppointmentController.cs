using HealthLink.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace HealthLink.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class AppointmentController : ControllerBase
{
    private readonly IAppointmentService _appointmentService;
    private readonly ISchedulingService _schedulingService;

    public AppointmentController(
        IAppointmentService appointmentService,
        ISchedulingService schedulingService)
    {
        _appointmentService = appointmentService;
        _schedulingService = schedulingService;
    }

    [HttpGet("{id}")]
    public IActionResult GetAppointment(int id)
    {
        var appointment = _appointmentService.GetByIdAsync(id).Result;
        if (appointment == null)
            return NotFound();
        return Ok(appointment);
    }

    [HttpGet]
    public async Task<IActionResult> GetAllAppointments()
    {
        var appointments = await _appointmentService.GetAllAsync();
        return Ok(appointments);
    }

    [HttpPost]
    public async Task<IActionResult> CreateAppointment([FromBody] CreateAppointmentRequest request)
    {
        var result = await _schedulingService.ScheduleAppointmentAsync(request.PatientId, request.DateTime, request.DoctorId);
        return result != null ? Ok(result) : BadRequest("Scheduling failed");
    }
}

public record CreateAppointmentRequest(int PatientId, DateTime DateTime, int DoctorId);
