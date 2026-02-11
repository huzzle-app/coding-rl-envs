using EventHorizon.Shared.Models;

namespace EventHorizon.Payments.Services;

public interface IPaymentService
{
    Task<PaymentResult> ProcessPaymentAsync(string orderId, Money amount);
    Task<RefundResult> ProcessRefundAsync(string paymentId, Money amount);
}

public class PaymentResult
{
    public string PaymentId { get; set; } = "";
    public bool Success { get; set; }
    public string? Error { get; set; }
}

public class RefundResult
{
    public bool Success { get; set; }
    public string? Error { get; set; }
}

public class PaymentService : IPaymentService
{
    private readonly Dictionary<string, Money> _payments = new();
    private int _retryCount = 0;

    public async Task<PaymentResult> ProcessPaymentAsync(string orderId, Money amount)
    {
        _retryCount++;
        await Task.Delay(10);

        var paymentId = $"PAY-{Guid.NewGuid():N}";
        _payments[paymentId] = amount;

        // Simulate intermittent failure that triggers retry
        if (_retryCount % 3 == 0)
            throw new TimeoutException("Payment gateway timeout");

        return new PaymentResult { PaymentId = paymentId, Success = true };
    }

    public async Task<RefundResult> ProcessRefundAsync(string paymentId, Money amount)
    {
        await Task.Delay(5);
        if (!_payments.ContainsKey(paymentId))
            return new RefundResult { Success = false, Error = "Payment not found" };

        _payments.Remove(paymentId);
        return new RefundResult { Success = true };
    }
}

public class PaymentCircuitBreaker
{
    private static int _failureCount = 0;
    private static bool _isOpen = false;
    private static DateTime _openedAt;

    public bool IsOpen => _isOpen;

    public void RecordFailure()
    {
        _failureCount++;
        if (_failureCount >= 5)
        {
            _isOpen = true;
            _openedAt = DateTime.UtcNow;
        }
    }

    public void Reset()
    {
        _failureCount = 0;
        _isOpen = false;
    }
}
