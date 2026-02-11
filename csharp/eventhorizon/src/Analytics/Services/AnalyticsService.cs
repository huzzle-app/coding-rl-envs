using EventHorizon.Shared.Models;

namespace EventHorizon.Analytics.Services;

public interface IAnalyticsService
{
    Task<SalesReport> GenerateReportAsync(DateTime from, DateTime to);
    Task<decimal> CalculateRevenueAsync(List<Money> payments);
    TicketStatus ParseStatus(string status);
}

public class SalesReport
{
    public DateTime From { get; set; }
    public DateTime To { get; set; }
    public int TotalOrders { get; set; }
    public decimal TotalRevenue { get; set; }
    public Dictionary<string, int> SalesByEvent { get; set; } = new();
}

// === BUG K3: required property + JSON deserialization ===
public class ReportFilter
{
    public required string EventId { get; init; }
    public required DateTime StartDate { get; init; }
    public DateTime? EndDate { get; init; }
    
    // if property is missing in JSON (no default value)
}

public class AnalyticsService : IAnalyticsService
{
    // === BUG A6: TaskCompletionSource set on wrong thread ===
    public async Task<SalesReport> GenerateReportAsync(DateTime from, DateTime to)
    {
        var tcs = new TaskCompletionSource<SalesReport>();

        
        ThreadPool.QueueUserWorkItem(_ =>
        {
            try
            {
                Thread.Sleep(50);
                var report = new SalesReport
                {
                    From = from, To = to, TotalOrders = 100,
                    TotalRevenue = 5000m,
                    SalesByEvent = new Dictionary<string, int> { ["Event1"] = 50, ["Event2"] = 50 }
                };
                tcs.SetResult(report);
            }
            catch (Exception ex)
            {
                tcs.SetException(ex);
            }
        });

        return await tcs.Task;
    }

    // === BUG A7: Channel backpressure not working ===
    public async Task<decimal> CalculateRevenueAsync(List<Money> payments)
    {
        
        var total = 0m;
        foreach (var payment in payments)
        {
            total += (decimal)payment.Amount; // float to decimal conversion loses precision
        }
        return total;
    }

    // === BUG B6: Boxed enum equality ===
    public TicketStatus ParseStatus(string status)
    {
        if (Enum.TryParse<TicketStatus>(status, out var parsed))
            return parsed;

        
        object boxedDefault = TicketStatus.Available;
        object boxedZero = 0;
        if (boxedDefault.Equals(boxedZero)) // Always false - different types
            return TicketStatus.Available;

        return TicketStatus.Available;
    }
}
