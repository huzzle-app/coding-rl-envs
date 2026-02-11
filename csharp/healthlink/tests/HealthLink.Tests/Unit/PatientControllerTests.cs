using FluentAssertions;
using HealthLink.Api.Controllers;
using HealthLink.Api.Models;
using HealthLink.Api.Services;
using Microsoft.AspNetCore.Mvc;
using Moq;
using Xunit;

namespace HealthLink.Tests.Unit;

public class PatientControllerTests
{
    private readonly Mock<IPatientService> _patientServiceMock;
    private readonly PatientController _controller;

    public PatientControllerTests()
    {
        _patientServiceMock = new Mock<IPatientService>();
        _controller = new PatientController(_patientServiceMock.Object);
    }

    [Fact]
    public async Task test_get_all_patients_returns_ok()
    {
        _patientServiceMock.Setup(s => s.GetAllAsync())
            .ReturnsAsync(new List<Patient>());
        var result = await _controller.GetAllPatients();
        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task test_get_patient_returns_ok()
    {
        _patientServiceMock.Setup(s => s.GetByIdAsync(1))
            .ReturnsAsync(new Patient { Id = 1, Name = "Test", Email = "t@t.com" });
        var result = await _controller.GetPatient(1);
        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task test_get_patient_not_found()
    {
        _patientServiceMock.Setup(s => s.GetByIdAsync(99))
            .ReturnsAsync((Patient?)null);
        var result = await _controller.GetPatient(99);
        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task test_delete_patient_returns_no_content()
    {
        var result = await _controller.DeletePatient(1);
        result.Should().BeOfType<NoContentResult>();
    }
}
