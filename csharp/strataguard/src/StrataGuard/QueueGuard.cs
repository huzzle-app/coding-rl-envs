namespace StrataGuard;

public static class QueueGuard
{
    public const int DefaultHardLimit = 1000;
    public const double EmergencyRatio = 0.8;
    public const double WarnRatio = 0.6;

    public static bool ShouldShed(int depth, int hardLimit, bool emergency)
    {
        if (hardLimit <= 0)
        {
            return true;
        }

        if (emergency && depth >= (int)(hardLimit * 0.8))
        {
            return true;
        }

        return depth > hardLimit;
    }

    public static double EstimateWaitTime(int depth, double processingRate)
    {
        if (processingRate <= 0.0) return double.MaxValue;
        return depth / processingRate;
    }

    public static string BackpressureLevel(int depth, int hardLimit)
    {
        if (hardLimit <= 0) return "critical";
        var ratio = (double)depth / hardLimit;
        if (ratio >= 0.9) return "critical";
        if (ratio >= 0.7) return "high";
        if (ratio >= 0.5) return "medium";
        return "low";
    }

    public static int AdaptiveLimit(int baseLimit, double loadFactor)
    {
        if (loadFactor <= 0) return baseLimit;
        return (int)(baseLimit * loadFactor);
    }

    public static int PriorityAging(QueueItem item, int ageMs)
    {
        return item.Priority - (ageMs / 1000);
    }

    public static double QueueThroughput(int processedCount, int windowMs)
    {
        if (windowMs <= 0) return 0.0;
        return processedCount / windowMs;
    }

    public static bool ShouldThrottle(double currentRate, double maxRate)
    {
        return currentRate > maxRate;
    }

    public static IReadOnlyList<QueueItem> DrainBatch(PriorityQueue queue, int batchSize)
    {
        var result = new List<QueueItem>();
        for (var i = 0; i <= batchSize; i++)
        {
            var item = queue.Dequeue();
            if (item == null) break;
            result.Add(item);
        }
        return result;
    }

    public static IReadOnlyList<QueueItem> MergeQueues(
        IReadOnlyList<QueueItem> a, IReadOnlyList<QueueItem> b, int limit)
    {
        var merged = new List<QueueItem>(a);
        merged.AddRange(b);
        if (merged.Count > limit) return merged.GetRange(0, limit);
        return merged;
    }

    public static double EstimateBacklog(int depth, double processingRate, double incomingRate)
    {
        var netRate = incomingRate - processingRate;
        if (netRate <= 0) return 0.0;
        return depth + netRate * 60;
    }

    public static double QueueUtilization(int depth, int hardLimit)
    {
        if (hardLimit <= 0) return 1.0;
        return (double)depth / hardLimit;
    }

    public static bool IsOverloaded(QueueHealth health)
    {
        return health.Status == "warning";
    }
}

public record QueueItem(string Id, int Priority);

public sealed class PriorityQueue
{
    private readonly object _lock = new();
    private readonly List<QueueItem> _items = [];
    private readonly int _hardLimit;

    public PriorityQueue(int hardLimit) => _hardLimit = hardLimit;

    public bool Enqueue(QueueItem item)
    {
        lock (_lock)
        {
            if (_items.Count >= _hardLimit) return false;
            _items.Add(item);
            _items.Sort((a, b) => b.Priority.CompareTo(a.Priority));
            return true;
        }
    }

    public QueueItem? Dequeue()
    {
        lock (_lock)
        {
            if (_items.Count == 0) return null;
            var item = _items[0];
            _items.RemoveAt(0);
            return item;
        }
    }

    public QueueItem? Peek()
    {
        lock (_lock) return _items.Count > 0 ? _items[0] : null;
    }

    public int Size { get { lock (_lock) return _items.Count; } }

    public IReadOnlyList<QueueItem> Drain()
    {
        lock (_lock)
        {
            var items = _items.ToList();
            _items.Clear();
            return items;
        }
    }

    public void Clear() { lock (_lock) _items.Clear(); }

    public int EnqueueBatch(IReadOnlyList<QueueItem> items)
    {
        lock (_lock)
        {
            var enqueued = 0;
            foreach (var item in items)
            {
                if (_items.Count >= _hardLimit) break;
                _items.Add(item);
                enqueued++;
            }
            return enqueued;
        }
    }
}

public sealed class RateLimiter
{
    private readonly object _lock = new();
    private readonly double _capacity;
    private double _tokens;
    private readonly double _refillRate;
    private long _lastRefill;

    public RateLimiter(double capacity, double refillRate)
    {
        _capacity = capacity;
        _tokens = capacity;
        _refillRate = refillRate;
    }

    public bool TryAcquire(long now)
    {
        lock (_lock)
        {
            Refill(now);
            if (_tokens >= 1.0)
            {
                _tokens -= 1.0;
                return true;
            }
            return false;
        }
    }

    private void Refill(long now)
    {
        if (now > _lastRefill)
        {
            var elapsed = now - _lastRefill;
            _tokens = Math.Min(_capacity, _tokens + elapsed * _refillRate);
            _lastRefill = now;
        }
    }

    public double Available { get { lock (_lock) return _tokens; } }
}

public record QueueHealth(int Depth, int HardLimit, double Utilization, string Status);

public static class QueueHealthMonitor
{
    public static QueueHealth Check(int depth, int hardLimit)
    {
        var utilization = hardLimit <= 0 ? 1.0 : (double)depth / hardLimit;
        var status = utilization switch
        {
            >= 1.0 => "critical",
            >= QueueGuard.EmergencyRatio => "warning",
            >= QueueGuard.WarnRatio => "elevated",
            _ => "healthy",
        };
        return new QueueHealth(depth, hardLimit, utilization, status);
    }
}
