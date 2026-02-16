using FluentAssertions;
using HealthLink.Api.Controllers;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Xunit;

namespace HealthLink.Tests.Security;

public class PathTraversalTests
{
    [Fact]
    public void test_path_combine_injection_blocked()
    {
        
        var controller = new DocumentController();
        var result = controller.DownloadDocument("/etc/passwd");

        // After fix, should reject paths that escape upload directory
        result.Should().NotBeOfType<FileContentResult>();
    }

    [Fact]
    public void test_path_traversal_prevented()
    {
        
        var controller = new DocumentController();
        var result = controller.DownloadDocument("../../../etc/passwd");
        result.Should().NotBeOfType<FileContentResult>();
    }

    [Fact]
    public void test_normal_filename_allowed()
    {
        var controller = new DocumentController();
        // Normal filename should work (though file won't exist in test)
        var result = controller.DownloadDocument("document.pdf");
        result.Should().BeOfType<NotFoundObjectResult>();
    }

    [Fact]
    public void test_absolute_path_blocked()
    {
        // Verify that DocumentController validates the resolved path stays within upload directory
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Controllers", "DocumentController.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        // The controller should validate the final path (e.g., using GetFullPath, StartsWith, etc.)
        var hasPathValidation = source.Contains("GetFullPath") ||
                               source.Contains("StartsWith") ||
                               source.Contains("Path.GetRelativePath") ||
                               source.Contains("IsPathRooted");
        hasPathValidation.Should().BeTrue(
            "DocumentController must validate that the resolved file path stays within the upload directory");
    }

    [Fact]
    public void test_encoded_traversal_blocked()
    {
        var controller = new DocumentController();
        var result = controller.DownloadDocument("..%2F..%2Fetc%2Fpasswd");
        result.Should().NotBeOfType<FileContentResult>();
    }
}
