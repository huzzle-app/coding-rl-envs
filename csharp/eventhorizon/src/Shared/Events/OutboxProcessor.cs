namespace EventHorizon.Shared.Events;

public interface IOutboxProcessor
{
    Task ProcessPendingMessagesAsync(CancellationToken ct);
    Task EnqueueAsync(string messageType, string payload);
}

public class OutboxMessage
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string MessageType { get; set; } = "";
    public string Payload { get; set; } = "";
    public bool Processed { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

public class OutboxProcessor : IOutboxProcessor
{
    private readonly List<OutboxMessage> _outbox = new();
    private readonly IEventBus _eventBus;

    public OutboxProcessor(IEventBus eventBus)
    {
        _eventBus = eventBus;
    }

    public Task EnqueueAsync(string messageType, string payload)
    {
        _outbox.Add(new OutboxMessage { MessageType = messageType, Payload = payload });
        return Task.CompletedTask;
    }

    // === BUG H5: Outbox duplication - not marking as processed before publishing ===
    // If publish succeeds but marking fails, the message will be published again
    public async Task ProcessPendingMessagesAsync(CancellationToken ct)
    {
        var pending = _outbox.Where(m => !m.Processed).ToList();
        foreach (var msg in pending)
        {
            await _eventBus.PublishAsync(new OutboxEvent { Type = msg.MessageType, Payload = msg.Payload });
            
            msg.Processed = true;
        }
    }
}

public class OutboxEvent
{
    public string Type { get; set; } = "";
    public string Payload { get; set; } = "";
}
