namespace EventHorizon.Shared;

public interface IEventBus
{
    Task PublishAsync<T>(T @event) where T : class;
    Task SubscribeAsync<T>(Func<T, Task> handler) where T : class;
}


public class EventBus : IEventBus
{
    private readonly Config.INotificationDispatcher _dispatcher;
    private readonly Dictionary<Type, List<Delegate>> _handlers = new();

    public EventBus(Config.INotificationDispatcher dispatcher)
    {
        _dispatcher = dispatcher;
    }

    public async Task PublishAsync<T>(T @event) where T : class
    {
        if (_handlers.TryGetValue(typeof(T), out var handlers))
        {
            foreach (var handler in handlers)
            {
                await ((Func<T, Task>)handler)(@event);
            }
        }
    }

    public Task SubscribeAsync<T>(Func<T, Task> handler) where T : class
    {
        if (!_handlers.ContainsKey(typeof(T)))
            _handlers[typeof(T)] = new List<Delegate>();
        _handlers[typeof(T)].Add(handler);
        return Task.CompletedTask;
    }
}
