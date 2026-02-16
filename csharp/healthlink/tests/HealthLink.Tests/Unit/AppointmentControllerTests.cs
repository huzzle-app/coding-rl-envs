using FluentAssertions;
using HealthLink.Api.Controllers;
using HealthLink.Api.Models;
using HealthLink.Api.Services;
using Microsoft.AspNetCore.Mvc;
using Moq;
using Xunit;

namespace HealthLink.Tests.Unit;

public class AppointmentControllerTests
{
    private readonly Mock<IAppointmentService> _appointmentServiceMock;
    private readonly Mock<ISchedulingService> _schedulingServiceMock;
    private readonly AppointmentController _controller;

    public AppointmentControllerTests()
    {
        _appointmentServiceMock = new Mock<IAppointmentService>();
        _schedulingServiceMock = new Mock<ISchedulingService>();
        _controller = new AppointmentController(
            _appointmentServiceMock.Object,
            _schedulingServiceMock.Object);
    }

    [Fact]
    public void test_no_task_result_deadlock()
    {
        // GetAppointment should be async (return Task<IActionResult>), not block with .Result
        var method = typeof(AppointmentController).GetMethod("GetAppointment");
        method.Should().NotBeNull();
        method!.ReturnType.Should().BeAssignableTo(typeof(Task),
            "GetAppointment should be async to avoid .Result deadlocks");
    }

    [Fact]
    public void test_async_controller_completes()
    {
        // Verify the controller action doesn't use synchronous .Result or .Wait()
        var sourceFile = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
            "src", "HealthLink.Api", "Controllers", "AppointmentController.cs");
        var source = System.IO.File.ReadAllText(sourceFile);
        source.Should().NotContain(".Result",
            "controller should use await instead of .Result to prevent deadlocks");
        source.Should().NotContain(".Wait()",
            "controller should use await instead of .Wait() to prevent deadlocks");
    }

    [Fact]
    public async Task test_get_all_appointments_returns_ok()
    {
        _appointmentServiceMock
            .Setup(s => s.GetAllAsync())
            .ReturnsAsync(new List<Appointment>());

        var result = await _controller.GetAllAppointments();
        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task test_get_appointment_not_found()
    {
        _appointmentServiceMock
            .Setup(s => s.GetByIdAsync(99))
            .ReturnsAsync((Appointment?)null);

        var result = _controller.GetAppointment(99);
        result.Should().BeOfType<NotFoundResult>();
    }

    [Fact]
    public async Task test_create_appointment_success()
    {
        _schedulingServiceMock
            .Setup(s => s.ScheduleAppointmentAsync(1, It.IsAny<DateTime>(), 1))
            .ReturnsAsync(new Appointment { Id = 1 });

        var request = new CreateAppointmentRequest(1, DateTime.UtcNow, 1);
        var result = await _controller.CreateAppointment(request);
        result.Should().BeOfType<OkObjectResult>();
    }

    [Fact]
    public async Task test_create_appointment_failure()
    {
        _schedulingServiceMock
            .Setup(s => s.ScheduleAppointmentAsync(1, It.IsAny<DateTime>(), 1))
            .ReturnsAsync((Appointment?)null);

        var request = new CreateAppointmentRequest(1, DateTime.UtcNow, 1);
        var result = await _controller.CreateAppointment(request);
        result.Should().BeOfType<BadRequestObjectResult>();
    }
}
