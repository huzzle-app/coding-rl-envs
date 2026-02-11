using HealthLink.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace HealthLink.Api.Controllers;

// === BUG I4: [AllowAnonymous] on class overrides [Authorize] on methods ===
// When [AllowAnonymous] is on the controller, individual [Authorize]
// attributes on actions are ignored - all endpoints become public
[ApiController]
[Route("api/[controller]")]
[AllowAnonymous]
public class PatientController : ControllerBase
{
    private readonly IPatientService _patientService;

    public PatientController(IPatientService patientService)
    {
        _patientService = patientService;
    }

    [HttpGet]
    public async Task<IActionResult> GetAllPatients()
    {
        var patients = await _patientService.GetAllAsync();
        return Ok(patients);
    }

    [HttpGet("{id}")]
    public async Task<IActionResult> GetPatient(int id)
    {
        var patient = await _patientService.GetByIdAsync(id);
        return patient != null ? Ok(patient) : NotFound();
    }

    // This should require authentication but [AllowAnonymous] on class overrides it
    [Authorize]
    [HttpDelete("{id}")]
    public async Task<IActionResult> DeletePatient(int id)
    {
        await _patientService.DeleteAsync(id);
        return NoContent();
    }

    // This should require admin role but [AllowAnonymous] on class overrides it
    [Authorize(Roles = "Admin")]
    [HttpPut("{id}/sensitive")]
    public async Task<IActionResult> UpdateSensitiveData(int id, [FromBody] object data)
    {
        await _patientService.UpdateSensitiveDataAsync(id, data);
        return NoContent();
    }
}
