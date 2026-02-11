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
    public async Task test_no_task_result_deadlock()
    {
        
        _appointmentServiceMock
            .Setup(s => s.GetByIdAsync(1))
            .ReturnsAsync(new Appointment { Id = 1, Status = AppointmentStatus.Scheduled });

        // This test verifies that the controller action completes without deadlock
        // With the bug, calling .Result on an async method deadlocks
        var act = () => Task.Run(() => _controller.GetAppointment(1));
        var result = await act.Should().CompleteWithinAsync(TimeSpan.FromSeconds(5));
    }

    [Fact]
    public async Task test_async_controller_completes()
    {
        
        _appointmentServiceMock
            .Setup(s => s.GetByIdAsync(1))
            .ReturnsAsync(new Appointment { Id = 1, Status = AppointmentStatus.Scheduled });

        // Should complete without deadlock
        var result = _controller.GetAppointment(1);
        result.Should().NotBeNull();
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
