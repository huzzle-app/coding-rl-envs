namespace EventHorizon.Notifications.Hubs;

public interface INotificationClient
{
    Task ReceiveNotification(string message);
    Task ReceiveOrderUpdate(string orderId, string status);
}

// === BUG F2: SignalR connection leak - OnDisconnectedAsync not cleaning up ===
public class NotificationHub
{
    // Simulated hub (real SignalR Hub requires more infrastructure)
    private static readonly Dictionary<string, string> _connections = new();
    private static readonly List<string> _connectionPool = new(); 

    public Task OnConnectedAsync(string connectionId, string userId)
    {
        _connections[connectionId] = userId;
        _connectionPool.Add(connectionId); 
        return Task.CompletedTask;
    }

    
    public Task OnDisconnectedAsync(string connectionId)
    {
        _connections.Remove(connectionId);
        // Missing: _connectionPool.Remove(connectionId);
        return Task.CompletedTask;
    }

    public int GetActiveConnectionCount() => _connectionPool.Count; // Returns stale count
    public int GetRealConnectionCount() => _connections.Count;
}

// === BUG F4: HubContext misuse - sending from wrong context ===
public class HubNotificationSender
{
    private readonly NotificationHub _hub;

    public HubNotificationSender(NotificationHub hub)
    {
        _hub = hub;
    }

    
    public async Task NotifyUserAsync(string userId, string message)
    {
        await Task.Delay(5);
        // In real code, should use IHubContext<NotificationHub>
        // Using hub instance directly doesn't work outside hub pipeline
    }
}
