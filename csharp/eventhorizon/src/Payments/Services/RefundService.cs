using EventHorizon.Shared.Models;

namespace EventHorizon.Payments.Services;

public interface IRefundService
{
    Task<bool> QueueRefundAsync(string paymentId, Money amount);
    Task ProcessRefundQueueAsync();
}

public class RefundService : IRefundService
{
    private readonly List<(string PaymentId, Money Amount)> _queue = new();
    // === BUG D5: MemoryStream not returned to pool ===
    private readonly List<MemoryStream> _receiptStreams = new();

    public async Task<bool> QueueRefundAsync(string paymentId, Money amount)
    {
        await Task.Delay(5);
        _queue.Add((paymentId, amount));

        
        var stream = new MemoryStream();
        var writer = new StreamWriter(stream);
        await writer.WriteAsync($"Refund receipt: {paymentId} - {amount.Amount} {amount.Currency}");
        await writer.FlushAsync();
        _receiptStreams.Add(stream); // Never disposed!

        return true;
    }

    // === BUG E6: SaveChanges ordering - dependent saved first ===
    public async Task ProcessRefundQueueAsync()
    {
        await Task.Delay(10);
        
        // A refund for a partial order might need the full order settled first
        foreach (var (paymentId, amount) in _queue.ToList())
        {
            _queue.Remove((paymentId, amount));
        }
    }
}
