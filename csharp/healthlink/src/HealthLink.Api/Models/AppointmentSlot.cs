namespace HealthLink.Api.Models;

// === BUG B2: Struct mutation through interface ===
// When a struct implements an interface and is accessed via that interface,
// the struct is boxed. Mutations through the interface modify the boxed copy,
// not the original struct value.

public interface ISlot
{
    int Hour { get; set; }
    int Duration { get; set; }
    bool IsAvailable { get; set; }
}

public struct AppointmentSlot : ISlot
{
    public int Hour { get; set; }
    public int Duration { get; set; }
    public bool IsAvailable { get; set; }

    public AppointmentSlot(int hour, int duration, bool isAvailable)
    {
        Hour = hour;
        Duration = duration;
        IsAvailable = isAvailable;
    }

    public void MarkUnavailable()
    {
        IsAvailable = false;
    }
}

// Helper that demonstrates the bug
public static class SlotManager
{
    public static void UpdateSlotViaInterface(ISlot slot)
    {
        
        slot.IsAvailable = false;
        slot.Hour = 0;
    }

    public static List<ISlot> GetDailySlots()
    {
        var slots = new List<ISlot>();
        for (int h = 9; h < 17; h++)
        {
            // Each struct is boxed when added to List<ISlot>
            slots.Add(new AppointmentSlot(h, 60, true));
        }
        return slots;
    }
}
