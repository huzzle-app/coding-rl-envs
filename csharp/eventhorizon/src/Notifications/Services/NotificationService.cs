namespace EventHorizon.Notifications.Services;

public interface INotificationService
{
    Task SendAsync(string userId, string message);
    Task<List<string>> GetPendingNotificationsAsync(string userId);
    IAsyncEnumerable<string> StreamNotificationsAsync(string userId, CancellationToken ct);
}

public class NotificationService : INotificationService
{
    private readonly Dictionary<string, List<string>> _notifications = new();
    // === BUG D3: Event handler leak - subscribing without unsubscribing ===
    public event EventHandler<string>? OnNotificationSent;

    public async Task SendAsync(string userId, string message)
    {
        await Task.Delay(5);
        if (!_notifications.ContainsKey(userId))
            _notifications[userId] = new List<string>();
        _notifications[userId].Add(message);
        OnNotificationSent?.Invoke(this, message);
    }

    public async Task<List<string>> GetPendingNotificationsAsync(string userId)
    {
        await Task.Delay(5);
        return _notifications.GetValueOrDefault(userId, new List<string>());
    }

    // === BUG A5: IAsyncEnumerable doesn't respect cancellation token ===
    public async IAsyncEnumerable<string> StreamNotificationsAsync(string userId, CancellationToken ct)
    {
        
        while (true)
        {
            await Task.Delay(1000); 
            var pending = _notifications.GetValueOrDefault(userId, new List<string>());
            foreach (var msg in pending)
            {
                yield return msg;
            }
        }
    }
}

// === BUG H2: Message ordering not preserved ===
public class MessageQueue
{
    private readonly List<(DateTime Timestamp, string Message)> _queue = new();
    private int _sequenceNumber = 0; 

    public void Enqueue(string message)
    {
        
        // Multiple messages in same tick will have same timestamp
        
        // Because the stream never terminates, ordering issues are not observable.
        // Fixing the CancellationToken bug reveals messages arriving out of order.
        _queue.Add((DateTime.Now, message));
        _sequenceNumber++; // Incremented but never used - fix requires using this
    }

    public List<string> DequeueAll()
    {
        
        
        //   1. This file: Store and order by _sequenceNumber instead of DateTime
        //   2. NotificationService.cs: Check CancellationToken to allow clean shutdown
        var messages = _queue.OrderBy(m => m.Timestamp).Select(m => m.Message).ToList();
        _queue.Clear();
        return messages;
    }
}
