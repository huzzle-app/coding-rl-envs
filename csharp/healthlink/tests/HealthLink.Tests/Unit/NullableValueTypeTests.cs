using FluentAssertions;
using HealthLink.Api.Models;
using Xunit;

namespace HealthLink.Tests.Unit;

public class NullableValueTypeTests
{
    [Fact]
    public void test_struct_mutation_through_interface()
    {
        
        var slot = new AppointmentSlot(10, 60, true);
        ISlot interfaceSlot = slot;
        SlotManager.UpdateSlotViaInterface(interfaceSlot);

        // After fix, the original should be unchanged (struct semantics)
        // but the bug is that code EXPECTS the mutation to work through interface
        slot.IsAvailable.Should().BeTrue("original struct should not be modified through interface");
    }

    [Fact]
    public void test_appointment_slot_value_preserved()
    {
        
        var slot = new AppointmentSlot(14, 30, true);
        ISlot boxed = slot;
        boxed.IsAvailable = false;
        slot.IsAvailable.Should().BeTrue("original struct is not affected by boxed copy mutation");
    }

    [Fact]
    public void test_default_struct_zero_values()
    {
        
        var slot = default(TimeSlot);
        slot.StartHour.Should().Be(0);
        slot.EndHour.Should().Be(0);
        slot.IsValid.Should().BeFalse("default TimeSlot should be invalid");
    }

    [Fact]
    public void test_timeslot_default_invalid()
    {
        
        var appointment = new Appointment
        {
            PatientId = 1, DoctorId = 1,
            DateTime = DateTime.UtcNow, Status = AppointmentStatus.Scheduled
        };
        // Slot is default(TimeSlot) with zero values
        appointment.Slot.IsValid.Should().BeFalse();
    }

    [Fact]
    public void test_valid_timeslot()
    {
        var slot = new TimeSlot { StartHour = 9, EndHour = 10 };
        slot.IsValid.Should().BeTrue();
        slot.Duration.Should().Be(TimeSpan.FromHours(1));
    }

    [Fact]
    public void test_slot_manager_daily_slots()
    {
        var slots = SlotManager.GetDailySlots();
        slots.Should().HaveCount(8);
        slots.All(s => s.IsAvailable).Should().BeTrue();
    }

    [Fact]
    public void test_appointment_slot_creation()
    {
        var slot = new AppointmentSlot(9, 60, true);
        slot.Hour.Should().Be(9);
        slot.Duration.Should().Be(60);
        slot.IsAvailable.Should().BeTrue();
    }

    [Fact]
    public void test_appointment_slot_mark_unavailable()
    {
        var slot = new AppointmentSlot(9, 60, true);
        slot.MarkUnavailable();
        slot.IsAvailable.Should().BeFalse();
    }
}
