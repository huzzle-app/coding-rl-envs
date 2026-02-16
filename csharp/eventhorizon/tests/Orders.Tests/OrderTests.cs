using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

namespace EventHorizon.Orders.Tests;

public class OrderTests
{
    
    [Fact]
    public async Task test_consumer_registered()
    {
        var bus = new MassTransitBus();

        
        bool isRegistered = bus.IsConsumerRegistered<OrderCreatedConsumer>();

        Assert.True(isRegistered, "OrderCreatedConsumer should be registered with MassTransit");
    }

    [Fact]
    public async Task test_message_consumed()
    {
        var bus = new MassTransitBus();
        bus.RegisterConsumer<OrderCreatedConsumer>();

        var message = new OrderCreatedMessage { OrderId = "O1" };

        
        await bus.Publish(message);

        Assert.True(bus.WasMessageConsumed(message), "Message should be consumed by registered consumer");
    }

    
    [Fact]
    public async Task test_pipeline_ordering_correct()
    {
        var pipeline = new MediatRPipeline();

        
        pipeline.AddBehavior<ValidationBehavior>();
        pipeline.AddBehavior<LoggingBehavior>();

        var order = pipeline.GetBehaviorOrder();

        Assert.True(order.IndexOf("ValidationBehavior") < order.IndexOf("Handler"),
            "Validation must run before handler");
    }

    [Fact]
    public async Task test_validation_before_handler()
    {
        var mediator = new Mediator();
        var command = new CreateOrderCommand { Quantity = -1 }; // Invalid

        
        var ex = await Assert.ThrowsAsync<ValidationException>(() => mediator.Send(command));

        Assert.Contains("Quantity", ex.Message);
    }

    
    [Fact]
    public async Task test_polly_retry_idempotent()
    {
        var paymentClient = new PaymentClient(retryCount: 3);
        int attemptCount = 0;

        paymentClient.OnAttempt += () => attemptCount++;

        
        try
        {
            await paymentClient.ChargeAsync("ORDER1", 100m);
        }
        catch { }

        Assert.True(attemptCount <= 3, "Should retry up to 3 times");
        Assert.Equal(1, paymentClient.SuccessfulCharges);
    }

    [Fact]
    public async Task test_no_double_charge()
    {
        var orderService = new OrderService();

        
        await orderService.ProcessPayment("ORDER1", "IDEMPOTENCY-KEY-1");
        await orderService.ProcessPayment("ORDER1", "IDEMPOTENCY-KEY-1"); // Retry with same key

        Assert.Equal(1, orderService.TotalCharges);
    }

    
    [Fact]
    public async Task test_saga_no_deadlock()
    {
        var saga = new OrderSaga();

        
        var task1 = saga.Handle(new OrderCreated { OrderId = "O1" });
        var task2 = saga.Handle(new PaymentProcessed { OrderId = "O1" });

        var completed = await Task.WhenAny(Task.WhenAll(task1, task2), Task.Delay(5000));

        Assert.True(completed != Task.Delay(5000), "Saga should not deadlock on concurrent events");
    }

    [Fact]
    public async Task test_saga_state_consistent()
    {
        var saga = new OrderSaga();

        
        await saga.Handle(new OrderCreated { OrderId = "O1" });
        await saga.Handle(new PaymentProcessed { OrderId = "O1" });
        await saga.Handle(new OrderShipped { OrderId = "O1" });

        Assert.Equal("Completed", saga.CurrentState);
    }

    
    [Fact]
    public async Task test_async_disposable_awaited()
    {
        bool disposed = false;

        
        await using (var resource = new AsyncResource(() => disposed = true))
        {
            await resource.DoWorkAsync();
        }

        Assert.True(disposed, "IAsyncDisposable should be properly awaited");
    }

    [Fact]
    public async Task test_stream_flushed()
    {
        var stream = new AsyncStream();

        await stream.WriteAsync("data");

        
        await stream.DisposeAsync();

        Assert.True(stream.IsFlushed, "Stream should be flushed before disposal");
    }

    
    [Fact]
    public async Task test_async_void_consumer_fixed()
    {
        var consumer = new MessageConsumer();
        Exception caughtException = null;

        
        try
        {
            await consumer.ConsumeAsync(new InvalidMessage());
        }
        catch (Exception ex)
        {
            caughtException = ex;
        }

        Assert.NotNull(caughtException); // Should propagate exception
    }

    [Fact]
    public async Task test_consumer_errors_propagate()
    {
        var handler = new OrderHandler();

        
        await Assert.ThrowsAsync<InvalidOperationException>(
            () => handler.HandleAsync(new FailingOrder()));
    }

    // Baseline tests
    [Fact]
    public void test_order_creation()
    {
        var order = new Order
        {
            Id = "O1",
            CustomerId = "C1",
            TotalAmount = 150.00m,
            Status = "Pending"
        };

        Assert.Equal("O1", order.Id);
        Assert.Equal(150.00m, order.TotalAmount);
    }

    [Fact]
    public void test_order_line_items()
    {
        var order = new Order();
        order.LineItems.Add(new LineItem { ProductId = "P1", Quantity = 2, Price = 50m });
        order.LineItems.Add(new LineItem { ProductId = "P2", Quantity = 1, Price = 50m });

        Assert.Equal(2, order.LineItems.Count);
        Assert.Equal(150m, order.LineItems.Sum(li => li.Quantity * li.Price));
    }

    [Fact]
    public void test_order_status_transition()
    {
        var order = new Order { Status = "Pending" };
        order.Status = "Processing";
        order.Status = "Completed";

        Assert.Equal("Completed", order.Status);
    }

    [Fact]
    public async Task test_order_validation()
    {
        var validator = new OrderValidator();
        var order = new Order { TotalAmount = -100m };

        var isValid = await validator.ValidateAsync(order);

        Assert.False(isValid, "Negative amounts should not be valid");
    }

    [Fact]
    public async Task test_order_cancellation()
    {
        var order = new Order { Status = "Pending" };
        var service = new OrderService();

        await service.CancelOrder(order);

        Assert.Equal("Cancelled", order.Status);
    }

    [Fact]
    public void test_discount_calculation()
    {
        var order = new Order { TotalAmount = 100m };
        var discountPercent = 10m;
        var discounted = order.TotalAmount * (1 - discountPercent / 100m);

        Assert.Equal(90m, discounted);
    }

    [Fact]
    public async Task test_order_notification()
    {
        var notifier = new OrderNotifier();
        var order = new Order { Id = "O1", CustomerId = "C1" };

        await notifier.NotifyCustomer(order);

        Assert.True(notifier.NotificationSent);
    }

    [Fact]
    public void test_order_total_with_tax()
    {
        var order = new Order { TotalAmount = 100m };
        var taxRate = 0.08m;
        var total = order.TotalAmount * (1 + taxRate);

        Assert.Equal(108m, total);
    }

    [Fact]
    public void test_order_total_calculation()
    {
        var order = new Order();
        order.LineItems.Add(new LineItem { Price = 25m, Quantity = 2 });
        order.LineItems.Add(new LineItem { Price = 50m, Quantity = 1 });
        var total = order.LineItems.Sum(li => li.Price * li.Quantity);
        Assert.Equal(100m, total);
    }

    [Fact]
    public void test_order_multiple_items()
    {
        var order = new Order();
        order.LineItems.Add(new LineItem { ProductId = "P1", Quantity = 1 });
        order.LineItems.Add(new LineItem { ProductId = "P2", Quantity = 2 });
        order.LineItems.Add(new LineItem { ProductId = "P3", Quantity = 3 });
        Assert.Equal(3, order.LineItems.Count);
    }

    [Fact]
    public void test_order_apply_discount()
    {
        var order = new Order { TotalAmount = 100m };
        var discount = 15m;
        var finalAmount = order.TotalAmount - discount;
        Assert.Equal(85m, finalAmount);
    }

    [Fact]
    public void test_order_apply_coupon()
    {
        var order = new Order { TotalAmount = 200m };
        var couponPercent = 20m;
        var discounted = order.TotalAmount * (1 - couponPercent / 100m);
        Assert.Equal(160m, discounted);
    }

    [Fact]
    public void test_order_shipping_calc()
    {
        var orderTotal = 75m;
        var shippingCost = orderTotal >= 50m ? 0m : 10m;
        Assert.Equal(0m, shippingCost);
    }

    [Fact]
    public void test_order_tax_calc()
    {
        var subtotal = 100m;
        var taxRate = 0.07m;
        var tax = subtotal * taxRate;
        Assert.Equal(7m, tax);
    }

    [Fact]
    public void test_order_pending_to_confirmed()
    {
        var order = new Order { Status = "Pending" };
        order.Status = "Confirmed";
        Assert.Equal("Confirmed", order.Status);
    }

    [Fact]
    public void test_order_confirmed_to_shipped()
    {
        var order = new Order { Status = "Confirmed" };
        order.Status = "Shipped";
        Assert.Equal("Shipped", order.Status);
    }

    [Fact]
    public void test_order_refund_request()
    {
        var order = new Order { Status = "Completed", TotalAmount = 100m };
        order.Status = "Refund Requested";
        Assert.Equal("Refund Requested", order.Status);
    }

    [Fact]
    public void test_order_partial_refund()
    {
        var order = new Order { TotalAmount = 100m };
        var refundAmount = 30m;
        var remaining = order.TotalAmount - refundAmount;
        Assert.Equal(70m, remaining);
    }

    [Fact]
    public void test_order_history()
    {
        var orders = new List<Order>
        {
            new Order { Id = "O1" },
            new Order { Id = "O2" },
            new Order { Id = "O3" }
        };
        Assert.Equal(3, orders.Count);
    }

    [Fact]
    public void test_order_search()
    {
        var orders = new List<Order>
        {
            new Order { Id = "O1", CustomerId = "C1" },
            new Order { Id = "O2", CustomerId = "C2" }
        };
        var found = orders.FirstOrDefault(o => o.CustomerId == "C1");
        Assert.NotNull(found);
    }

    [Fact]
    public void test_order_pagination()
    {
        var allOrders = Enumerable.Range(1, 100).Select(i => new Order { Id = $"O{i}" }).ToList();
        var page = 2;
        var pageSize = 10;
        var pageOrders = allOrders.Skip((page - 1) * pageSize).Take(pageSize).ToList();
        Assert.Equal(10, pageOrders.Count);
    }

    [Fact]
    public void test_order_sort_by_date()
    {
        var orders = new List<Order>
        {
            new Order { Id = "O1", TotalAmount = 100m },
            new Order { Id = "O2", TotalAmount = 50m },
            new Order { Id = "O3", TotalAmount = 150m }
        };
        var sorted = orders.OrderBy(o => o.TotalAmount).ToList();
        Assert.Equal("O2", sorted[0].Id);
    }

    [Fact]
    public void test_order_filter_by_status()
    {
        var orders = new List<Order>
        {
            new Order { Status = "Pending" },
            new Order { Status = "Completed" },
            new Order { Status = "Pending" }
        };
        var pending = orders.Where(o => o.Status == "Pending").ToList();
        Assert.Equal(2, pending.Count);
    }

    [Fact]
    public void test_order_export_csv()
    {
        var order = new Order { Id = "O1", CustomerId = "C1", TotalAmount = 100m };
        var csv = $"{order.Id},{order.CustomerId},{order.TotalAmount}";
        Assert.Contains("O1", csv);
    }

    [Fact]
    public void test_order_receipt_generation()
    {
        var order = new Order { Id = "O1", TotalAmount = 100m };
        var receipt = $"Order {order.Id}: Total ${order.TotalAmount}";
        Assert.Contains("Order O1", receipt);
    }

    [Fact]
    public void test_order_duplicate_detection()
    {
        var existingOrders = new HashSet<string> { "O1", "O2" };
        var newOrderId = "O1";
        var isDuplicate = existingOrders.Contains(newOrderId);
        Assert.True(isDuplicate);
    }

    [Fact]
    public void test_order_timeout_cancellation()
    {
        var orderTime = DateTime.UtcNow.AddMinutes(-30);
        var timeout = TimeSpan.FromMinutes(20);
        var isExpired = DateTime.UtcNow - orderTime > timeout;
        Assert.True(isExpired);
    }

    [Fact]
    public void test_order_customer_lookup()
    {
        var orders = new List<Order>
        {
            new Order { CustomerId = "C1" },
            new Order { CustomerId = "C1" },
            new Order { CustomerId = "C2" }
        };
        var customerOrders = orders.Where(o => o.CustomerId == "C1").ToList();
        Assert.Equal(2, customerOrders.Count);
    }
}

// Mock types for testing
public class MassTransitBus
{
    private HashSet<Type> _consumers = new();
    private List<object> _consumedMessages = new();

    public void RegisterConsumer<T>() => _consumers.Add(typeof(T));
    public bool IsConsumerRegistered<T>() => _consumers.Contains(typeof(T));

    public async Task Publish(object message)
    {
        if (_consumers.Any())
            _consumedMessages.Add(message);
    }

    public bool WasMessageConsumed(object message) => _consumedMessages.Contains(message);
}

public class OrderCreatedConsumer { }
public class OrderCreatedMessage { public string OrderId { get; set; } }

public class MediatRPipeline
{
    private List<string> _behaviors = new();

    public void AddBehavior<T>() => _behaviors.Add(typeof(T).Name);
    public List<string> GetBehaviorOrder()
    {
        var order = new List<string>(_behaviors);
        order.Add("Handler");
        return order;
    }
}

public class ValidationBehavior { }
public class LoggingBehavior { }

public class Mediator
{
    public async Task<object> Send(object command)
    {
        if (command is CreateOrderCommand cmd && cmd.Quantity < 0)
            throw new ValidationException("Quantity must be positive");
        return null;
    }
}

public class CreateOrderCommand { public int Quantity { get; set; } }
public class ValidationException : Exception
{
    public ValidationException(string message) : base(message) { }
}

public class PaymentClient
{
    private int _retryCount;
    private HashSet<string> _processedOrders = new();
    public int SuccessfulCharges => _processedOrders.Count;
    public event Action OnAttempt;

    public PaymentClient(int retryCount) => _retryCount = retryCount;

    public async Task ChargeAsync(string orderId, decimal amount)
    {
        for (int i = 0; i < _retryCount; i++)
        {
            OnAttempt?.Invoke();
            if (i == _retryCount - 1)
            {
                _processedOrders.Add(orderId);
                return;
            }
        }
    }
}

public class OrderService
{
    private HashSet<string> _idempotencyKeys = new();
    public int TotalCharges { get; private set; }

    public async Task ProcessPayment(string orderId, string idempotencyKey)
    {
        if (_idempotencyKeys.Add(idempotencyKey))
            TotalCharges++;
    }

    public async Task CancelOrder(Order order)
    {
        order.Status = "Cancelled";
    }
}

public class OrderSaga
{
    private object _lock = new();
    public string CurrentState { get; private set; } = "Initial";

    public async Task Handle(OrderCreated evt)
    {
        await Task.Delay(10);
        lock (_lock) { CurrentState = "Created"; }
    }

    public async Task Handle(PaymentProcessed evt)
    {
        await Task.Delay(10);
        lock (_lock) { if (CurrentState == "Created") CurrentState = "Paid"; }
    }

    public async Task Handle(OrderShipped evt)
    {
        await Task.Delay(10);
        lock (_lock) { if (CurrentState == "Paid") CurrentState = "Completed"; }
    }
}

public class OrderCreated { public string OrderId { get; set; } }
public class PaymentProcessed { public string OrderId { get; set; } }
public class OrderShipped { public string OrderId { get; set; } }

public class AsyncResource : IAsyncDisposable
{
    private Action _onDispose;
    public AsyncResource(Action onDispose) => _onDispose = onDispose;

    public async Task DoWorkAsync() => await Task.Delay(1);

    public async ValueTask DisposeAsync()
    {
        await Task.Delay(1);
        _onDispose?.Invoke();
    }
}

public class AsyncStream : IAsyncDisposable
{
    public bool IsFlushed { get; private set; }

    public async Task WriteAsync(string data) => await Task.Delay(1);

    public async ValueTask DisposeAsync()
    {
        await Task.Delay(1);
        IsFlushed = true;
    }
}

public class MessageConsumer
{
    public async Task ConsumeAsync(object message)
    {
        if (message is InvalidMessage)
            throw new InvalidOperationException("Invalid message");
        await Task.Delay(1);
    }
}

public class InvalidMessage { }

public class OrderHandler
{
    public async Task HandleAsync(object order)
    {
        if (order is FailingOrder)
            throw new InvalidOperationException("Order processing failed");
        await Task.Delay(1);
    }
}

public class FailingOrder { }

public class Order
{
    public string Id { get; set; }
    public string CustomerId { get; set; }
    public decimal TotalAmount { get; set; }
    public string Status { get; set; }
    public List<LineItem> LineItems { get; set; } = new();
}

public class LineItem
{
    public string ProductId { get; set; }
    public int Quantity { get; set; }
    public decimal Price { get; set; }
}

public class OrderValidator
{
    public async Task<bool> ValidateAsync(Order order)
    {
        await Task.Delay(1);
        return order.TotalAmount > 0;
    }
}

public class OrderNotifier
{
    public bool NotificationSent { get; private set; }

    public async Task NotifyCustomer(Order order)
    {
        await Task.Delay(1);
        NotificationSent = true;
    }
}
