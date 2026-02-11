using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EventHorizon.Auth.Controllers;

// === BUG I4: [AllowAnonymous] on class overrides [Authorize] on methods ===
[ApiController]
[Route("api/[controller]")]
[AllowAnonymous]
public class AuthController : ControllerBase
{
    [HttpPost("login")]
    public IActionResult Login([FromBody] LoginRequest request)
    {
        // Login should be anonymous - OK
        return Ok(new { Token = "mock-token" });
    }

    
    [Authorize]
    [HttpPost("change-password")]
    public IActionResult ChangePassword([FromBody] ChangePasswordRequest request)
    {
        return Ok(new { Success = true });
    }

    [Authorize(Roles = "Admin")]
    [HttpDelete("users/{id}")]
    public IActionResult DeleteUser(int id)
    {
        return NoContent();
    }
}

public record LoginRequest(string Email, string Password);
public record ChangePasswordRequest(string OldPassword, string NewPassword);
