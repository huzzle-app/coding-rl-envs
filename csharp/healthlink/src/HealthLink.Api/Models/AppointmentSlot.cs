namespace HealthLink.Api.Models;

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
            slots.Add(new AppointmentSlot(h, 60, true));
        }
        return slots;
    }
}
