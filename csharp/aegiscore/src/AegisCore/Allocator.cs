namespace AegisCore;

public static class Allocator
{
    public static IReadOnlyList<DispatchOrder> PlanDispatch(IEnumerable<DispatchOrder> orders, int capacity)
    {
        if (capacity <= 0)
        {
            return Array.Empty<DispatchOrder>();
        }

        
        return orders
            .OrderBy(o => o.Urgency)
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
            < 15 => 3.0,
            < 30 => 2.0,
            < 60 => 1.5,
            _ => 1.0,
        };

        return baseRate + severity * factor;
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
}

public record BerthSlot(string BerthId, int StartHour, int EndHour, bool Occupied, string? VesselId);

public static class BerthPlanner
{
    public static bool HasConflict(BerthSlot a, BerthSlot b)
    {
        if (a.BerthId != b.BerthId) return false;
        return a.StartHour <= b.EndHour && b.StartHour <= a.EndHour;
    }

    public static IReadOnlyList<BerthSlot> FindAvailableSlots(IEnumerable<BerthSlot> slots)
        => slots.Where(s => !s.Occupied).ToList();
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

public static class DispatchOptimizer
{
    public static double ComputeLoadFactor(int activePlanned, int totalCapacity)
    {
        if (totalCapacity <= 0) return 0.0;
        if (activePlanned >= totalCapacity) return 0.0;
        return (double)activePlanned / totalCapacity;
    }

    public static IReadOnlyList<(int WindowIndex, IReadOnlyList<DispatchOrder> Batch)> ScheduleTimeWindows(
        IEnumerable<DispatchOrder> orders, int windowCount, int capacityPerWindow)
    {
        if (windowCount <= 0 || capacityPerWindow <= 0)
            return Array.Empty<(int, IReadOnlyList<DispatchOrder>)>();

        var sorted = orders.OrderByDescending(o => o.Urgency)
            .ThenBy(o => o.SlaMinutes)
            .ToList();

        var windows = new List<(int, IReadOnlyList<DispatchOrder>)>();
        for (var w = 0; w < windowCount && sorted.Count > 0; w++)
        {
            var batch = sorted.Take(capacityPerWindow).ToList();
            sorted = sorted.Skip(capacityPerWindow).ToList();
            windows.Add((w, batch));
        }

        return windows;
    }

    public static IReadOnlyList<DispatchOrder> MergeDispatchPlans(
        IReadOnlyList<DispatchOrder> planA,
        IReadOnlyList<DispatchOrder> planB,
        int capacity)
    {
        var seen = new HashSet<string>();
        var merged = new List<DispatchOrder>();
        var combined = planA.Concat(planB)
            .OrderByDescending(o => o.Urgency)
            .ThenBy(o => o.SlaMinutes);

        foreach (var order in combined)
        {
            if (merged.Count >= capacity) break;
            if (seen.Add(order.Id))
                merged.Add(order);
        }

        return merged;
    }

    public static double EstimateBatchCost(IReadOnlyList<DispatchOrder> orders, double baseRate)
    {
        if (orders.Count == 0) return 0.0;
        var total = 0.0;
        for (var i = 0; i < orders.Count; i++)
        {
            var factor = 1.0 / (1 + i);
            total += Allocator.EstimateCost(orders[i].Urgency, orders[i].SlaMinutes, baseRate) * factor;
        }
        return Math.Round(total, 2);
    }
}

public record Lease(string ResourceId, string HolderId, long StartTime, long Duration)
{
    public long ExpiresAt => StartTime + Duration;
}

public sealed class LeaseManager
{
    private readonly object _lock = new();
    private readonly Dictionary<string, Lease> _leases = new();
    private readonly Dictionary<string, Queue<(string HolderId, long Duration, TaskCompletionSource<bool> Tcs)>> _waiters = new();

    public bool Acquire(string resourceId, string holderId, long now, long duration)
    {
        lock (_lock)
        {
            if (_leases.TryGetValue(resourceId, out var existing) && existing.ExpiresAt > now)
                return false;
            _leases[resourceId] = new Lease(resourceId, holderId, now, duration);
            return true;
        }
    }

    public bool Renew(string resourceId, string holderId, long now, long newDuration)
    {
        lock (_lock)
        {
            if (!_leases.TryGetValue(resourceId, out var lease)) return false;
            if (lease.HolderId != holderId) return false;
            if (lease.ExpiresAt <= now) return false;
            _leases[resourceId] = new Lease(resourceId, holderId, lease.StartTime, newDuration);
            return true;
        }
    }

    public bool Release(string resourceId, string holderId)
    {
        lock (_lock)
        {
            if (!_leases.TryGetValue(resourceId, out var lease)) return false;
            if (lease.HolderId != holderId) return false;
            _leases.Remove(resourceId);
            return true;
        }
    }

    public bool IsActive(string resourceId, long now)
    {
        lock (_lock) return _leases.TryGetValue(resourceId, out var l) && l.ExpiresAt > now;
    }

    public Lease? GetLease(string resourceId)
    {
        lock (_lock) return _leases.GetValueOrDefault(resourceId);
    }

    public int ActiveLeaseCount(long now)
    {
        lock (_lock) return _leases.Values.Count(l => l.ExpiresAt > now);
    }

    public IReadOnlyList<Lease> ExpiredLeases(long now)
    {
        lock (_lock) return _leases.Values.Where(l => l.ExpiresAt <= now).ToList();
    }
}

public sealed class CapacityPlanner
{
    private readonly LeaseManager _leases;
    private readonly int _totalBerths;
    private readonly Dictionary<string, double> _berthCapacities;

    public CapacityPlanner(LeaseManager leases, int totalBerths)
    {
        _leases = leases;
        _totalBerths = totalBerths;
        _berthCapacities = new Dictionary<string, double>();
        for (var i = 0; i < totalBerths; i++)
            _berthCapacities[$"berth-{i}"] = 1.0;
    }

    public double AvailableCapacity(long now)
    {
        var activeCount = _leases.ActiveLeaseCount(now);
        var loadFactor = DispatchOptimizer.ComputeLoadFactor(activeCount, _totalBerths);
        return (1.0 - loadFactor) * _totalBerths;
    }

    public bool CanAcceptDispatch(DispatchOrder order, long now)
    {
        var available = AvailableCapacity(now);
        return available >= 1.0;
    }

    public (bool Accepted, string? AssignedBerth) TryAssign(DispatchOrder order, long now, long leaseDuration)
    {
        if (!CanAcceptDispatch(order, now))
            return (false, null);

        for (var i = 0; i < _totalBerths; i++)
        {
            var berthId = $"berth-{i}";
            if (_leases.Acquire(berthId, order.Id, now, leaseDuration))
                return (true, berthId);
        }

        return (false, null);
    }

    public int TotalBerths => _totalBerths;
}
