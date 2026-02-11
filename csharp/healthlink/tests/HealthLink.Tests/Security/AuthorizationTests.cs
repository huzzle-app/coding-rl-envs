using FluentAssertions;
using HealthLink.Api.Controllers;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Reflection;
using Xunit;

namespace HealthLink.Tests.Security;

public class AuthorizationTests
{
    [Fact]
    public void test_allow_anonymous_not_overriding()
    {
        
        var controllerType = typeof(PatientController);
        var classAttrs = controllerType.GetCustomAttributes<AllowAnonymousAttribute>();

        // After fix, class should not have [AllowAnonymous]
        classAttrs.Should().BeEmpty("class-level [AllowAnonymous] overrides method-level [Authorize]");
    }

    [Fact]
    public void test_authenticated_endpoints_protected()
    {
        
        var deleteMethod = typeof(PatientController).GetMethod("DeletePatient");
        var authorizeAttr = deleteMethod!.GetCustomAttributes<AuthorizeAttribute>();
        authorizeAttr.Should().NotBeEmpty("DeletePatient should require authentication");
    }

    [Fact]
    public void test_admin_endpoints_require_role()
    {
        var updateMethod = typeof(PatientController).GetMethod("UpdateSensitiveData");
        var authorizeAttr = updateMethod!.GetCustomAttribute<AuthorizeAttribute>();
        authorizeAttr.Should().NotBeNull();
        authorizeAttr!.Roles.Should().Contain("Admin");
    }

    [Fact]
    public void test_appointment_controller_requires_auth()
    {
        var controllerType = typeof(AppointmentController);
        var authorizeAttr = controllerType.GetCustomAttributes<AuthorizeAttribute>();
        authorizeAttr.Should().NotBeEmpty();
    }

    [Fact]
    public void test_document_controller_requires_auth()
    {
        var controllerType = typeof(DocumentController);
        var authorizeAttr = controllerType.GetCustomAttributes<AuthorizeAttribute>();
        authorizeAttr.Should().NotBeEmpty();
    }
}
