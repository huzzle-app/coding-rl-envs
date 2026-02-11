using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace HealthLink.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class DocumentController : ControllerBase
{
    private readonly string _uploadDirectory = "/data/uploads";

    [HttpGet("download")]
    public IActionResult DownloadDocument([FromQuery] string filename)
    {
        // === BUG I3: Path.Combine with user input allows path traversal ===
        // Path.Combine("/uploads", "/etc/passwd") returns "/etc/passwd"
        // because the second argument is an absolute path that overrides the first
        var filePath = Path.Combine(_uploadDirectory, filename);

        if (!System.IO.File.Exists(filePath))
            return NotFound("File not found");

        var bytes = System.IO.File.ReadAllBytes(filePath);
        return File(bytes, "application/octet-stream", Path.GetFileName(filename));
    }

    [HttpPost("upload")]
    public async Task<IActionResult> UploadDocument(IFormFile file)
    {
        if (file == null || file.Length == 0)
            return BadRequest("No file uploaded");

        var filePath = Path.Combine(_uploadDirectory, file.FileName);
        using var stream = new FileStream(filePath, FileMode.Create);
        await file.CopyToAsync(stream);

        return Ok(new { FileName = file.FileName, Size = file.Length });
    }
}
