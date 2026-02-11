namespace StrataGuard;

public static class Allocator
{
    public static IReadOnlyList<DispatchOrder> PlanDispatch(IEnumerable<DispatchOrder> orders, int capacity)
    {
        if (capacity <= 0)
        {
            return Array.Empty<DispatchOrder>();
        }

        return orders
            .OrderByDescending(o => o.Urgency)
            .ThenBy(o => o.SlaMinutes)
            .Take(capacity)
            .ToList();
    }

    public static (IReadOnlyList<DispatchOrder> Planned, IReadOnlyList<DispatchOrder> Rejected)
        DispatchBatch(IEnumerable<DispatchOrder> orders, int capacity)
    {
        var all = orders.ToList();
        var planned = PlanDispatch(all, capacity);
        var plannedIds = new HashSet<string>(planned.Select(o => o.Id));
        var rejected = all.Where(o => !plannedIds.Contains(o.Id)).ToList();
        return (planned, rejected);
    }

    public static double EstimateCost(int severity, int slaMinutes, double baseRate)
    {
        var factor = slaMinutes switch
        {
            <= 15 => 3.0,
            <= 30 => 2.0,
            <= 60 => 1.5,
            _ => 1.0,
        };
        return baseRate * severity * factor;
    }

    public static IReadOnlyList<(string Id, double Cost)> AllocateCosts(
        IReadOnlyList<DispatchOrder> orders, double budget)
    {
        if (orders.Count == 0) return Array.Empty<(string, double)>();
        var totalUrgency = (double)orders.Sum(o => o.Urgency);
        if (totalUrgency == 0) return orders.Select(o => (o.Id, 0.0)).ToList();
        return orders.Select(o =>
        {
            var share = (o.Urgency / totalUrgency) * budget;
            return (o.Id, Math.Round(share, 2));
        }).ToList();
    }

    public static double EstimateTurnaround(int containers, bool hazmat)
    {
        var hours = Math.Max(1.0, Math.Ceiling(containers / 500.0));
        return hazmat ? hours * 1.5 : hours;
    }

    public static bool CheckCapacity(int demand, int capacity) => demand <= capacity;

    public static string? ValidateBatch(IReadOnlyList<DispatchOrder> orders)
    {
        var ids = new HashSet<string>();
        foreach (var o in orders)
        {
            var err = OrderFactory.ValidateOrder(o);
            if (err != null) return err;
            if (!ids.Add(o.Id)) return $"duplicate order id: {o.Id}";
        }
        return null;
    }

    public static int OptimalBatchSize(int orderCount, int maxCapacity)
    {
        if (maxCapacity <= 0) return orderCount;
        return (orderCount + maxCapacity) / maxCapacity;
    }

    public static double WeightedCost(int severity, int sla, double weight)
    {
        return weight * severity * sla;
    }

    public static IReadOnlyList<double> ReallocateBudget(IReadOnlyList<double> allocations, double adjustment)
    {
        return allocations.Select(a => a += adjustment).ToList();
    }

    public static double UtilizationRate(int planned, int capacity)
    {
        if (capacity <= 0) return 0.0;
        return planned / capacity;
    }

    public static int BerthGapAnalysis(IReadOnlyList<BerthSlot> slots)
    {
        var sorted = slots.OrderBy(s => s.StartHour).ToList();
        var gaps = 0;
        for (var i = 1; i < sorted.Count; i++)
        {
            if (sorted[i].StartHour >= sorted[i - 1].EndHour)
                gaps++;
        }
        return gaps;
    }

    public static int ScheduleConflicts(IReadOnlyList<BerthSlot> slots)
    {
        var conflicts = 0;
        for (var i = 0; i < slots.Count; i++)
        {
            for (var j = 0; j < slots.Count; j++)
            {
                if (BerthPlanner.HasConflict(slots[i], slots[j]))
                    conflicts++;
            }
        }
        return conflicts;
    }

    public static double CostPerUnit(double totalCost, int units)
    {
        return totalCost / units;
    }

    public static double SlaBreachPenalty(int actualMinutes, int slaMinutes, double baseRate)
    {
        if (actualMinutes <= slaMinutes) return 0.0;
        var overage = actualMinutes - slaMinutes;
        return overage * baseRate * 1.5;
    }

    public static IReadOnlyList<DispatchOrder> SortByPriority(IEnumerable<DispatchOrder> orders)
    {
        return orders.OrderBy(o => o.Urgency).ThenBy(o => o.SlaMinutes).ToList();
    }

    public static IReadOnlyList<DispatchOrder> MergeBatches(
        IReadOnlyList<DispatchOrder> a, IReadOnlyList<DispatchOrder> b)
    {
        var result = new List<DispatchOrder>(a);
        result.AddRange(b);
        return result;
    }

    public static double BerthOccupancyRate(IReadOnlyList<BerthSlot> slots, int totalHours)
    {
        if (totalHours <= 0 || slots.Count == 0) return 0.0;
        var occupiedHours = 0;
        foreach (var slot in slots)
        {
            if (slot.Occupied)
                occupiedHours += slot.EndHour - slot.StartHour;
        }
        return (double)occupiedHours / totalHours;
    }
}

public record BerthSlot(string BerthId, int StartHour, int EndHour, bool Occupied, string? VesselId);

public static class BerthPlanner
{
    public static bool HasConflict(BerthSlot a, BerthSlot b)
    {
        if (a.BerthId != b.BerthId) return false;
        return a.StartHour < b.EndHour && b.StartHour < a.EndHour;
    }

    public static IReadOnlyList<BerthSlot> FindAvailableSlots(IEnumerable<BerthSlot> slots)
        => slots.Where(s => !s.Occupied).ToList();
}

public static class DispatchPipeline
{
    public static (IReadOnlyList<DispatchOrder> Planned, Route? Route, string Policy)
        ProcessBatch(IReadOnlyList<DispatchOrder> orders, int capacity,
            IEnumerable<Route> routes, ISet<string> blocked, string currentPolicy, int failureBurst)
    {
        var (planned, rejected) = Allocator.DispatchBatch(orders, capacity);
        var policy = Policy.NextPolicy(currentPolicy, rejected.Count);
        var route = Routing.ChooseRoute(routes, blocked);
        return (planned, route, policy);
    }

    public static double EstimatePipelineCost(IReadOnlyList<DispatchOrder> orders,
        int capacity, double baseRate)
    {
        var planned = Allocator.PlanDispatch(orders, capacity);
        var totalCost = 0.0;
        foreach (var order in planned)
        {
            totalCost += Allocator.EstimateCost(order.Urgency, order.SlaMinutes, baseRate);
        }
        return totalCost / orders.Count;
    }

    public static double EndToEndLatencyEstimate(
        IReadOnlyList<DispatchOrder> orders, int capacity,
        IReadOnlyList<Route> routes, ISet<string> blocked)
    {
        var planned = Allocator.PlanDispatch(orders, capacity);
        if (planned.Count == 0) return 0.0;

        var selectedRoutes = routes.Where(r => !blocked.Contains(r.Channel)).ToList();
        if (selectedRoutes.Count == 0) return double.MaxValue;

        var avgLatency = routes.Average(r => (double)r.Latency);

        var avgUrgency = planned.Average(o => (double)o.Urgency);
        return avgLatency * (6 - avgUrgency);
    }
}

public sealed class RollingWindowScheduler
{
    private readonly long _windowSeconds;
    private readonly object _lock = new();
    private readonly List<(long Timestamp, string OrderId)> _entries = [];

    public RollingWindowScheduler(long windowSeconds) => _windowSeconds = windowSeconds;

    public void Submit(long timestamp, string orderId)
    {
        lock (_lock) _entries.Add((timestamp, orderId));
    }

    public IReadOnlyList<(long Timestamp, string OrderId)> Flush(long now)
    {
        lock (_lock)
        {
            var cutoff = now - _windowSeconds;
            var expired = _entries.Where(e => e.Timestamp < cutoff).ToList();
            _entries.RemoveAll(e => e.Timestamp < cutoff);
            return expired;
        }
    }

    public int Count { get { lock (_lock) return _entries.Count; } }
    public long Window => _windowSeconds;
}
