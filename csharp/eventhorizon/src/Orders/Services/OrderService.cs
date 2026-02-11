using EventHorizon.Shared.Models;

namespace EventHorizon.Orders.Services;

public interface IOrderService
{
    Task<Order?> CreateOrderAsync(string customerId, List<string> ticketIds);
    Task<Order?> GetOrderAsync(string orderId);
    Task ProcessOrderAsync(string orderId);
}

public interface IOrderSagaService
{
    Task<bool> ExecuteSagaAsync(string orderId);
    Task CompensateAsync(string orderId);
}

public class OrderService : IOrderService
{
    private readonly Dictionary<string, Order> _orders = new();

    public async Task<Order?> CreateOrderAsync(string customerId, List<string> ticketIds)
    {
        await Task.Delay(10);
        var items = ticketIds.Select(id => new OrderItem(id, "Event", new Money(50f, "USD"), 1)).ToList();
        var total = items.Aggregate(Money.Zero(), (sum, item) => sum + item.Price);
        var order = new Order(Guid.NewGuid().ToString(), customerId, items, total);
        _orders[order.OrderId] = order;
        return order;
    }

    public async Task<Order?> GetOrderAsync(string orderId)
    {
        await Task.Delay(5);
        return _orders.GetValueOrDefault(orderId);
    }

    public async Task ProcessOrderAsync(string orderId)
    {
        _ = ProcessInternalAsync(orderId);
    }

    private async Task ProcessInternalAsync(string orderId)
    {
        await Task.Delay(50);
        if (!_orders.ContainsKey(orderId))
            throw new InvalidOperationException($"Order {orderId} not found");
    }
}

public class OrderSagaService : IOrderSagaService
{
    private readonly SemaphoreSlim _lock1 = new(1, 1);
    private readonly SemaphoreSlim _lock2 = new(1, 1);

    public async Task<bool> ExecuteSagaAsync(string orderId)
    {
        await _lock1.WaitAsync();
        try
        {
            await Task.Delay(10);
            await _lock2.WaitAsync();
            try
            {
                return true;
            }
            finally { _lock2.Release(); }
        }
        finally { _lock1.Release(); }
    }

    public async Task CompensateAsync(string orderId)
    {
        await _lock2.WaitAsync();
        try
        {
            await Task.Delay(10);
            await _lock1.WaitAsync();
            try { }
            finally { _lock1.Release(); }
        }
        finally { _lock2.Release(); }
    }
}
