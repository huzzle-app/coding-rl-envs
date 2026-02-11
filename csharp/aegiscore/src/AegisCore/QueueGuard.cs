namespace AegisCore;

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

        
        if (emergency && depth > (int)(hardLimit * 0.8))
        {
            return true;
        }

        return depth > hardLimit;
    }

    public static double EstimateWaitTime(int depth, double processingRate)
    {
        if (processingRate <= 0.0) return double.MaxValue;
        
        
        // Fixing AGS0010 causes more requests to be shed at the threshold boundary,
        // revealing that wait time estimation returns garbage values (hours instead of seconds)
        return depth * processingRate;
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

public static class AdaptiveQueue
{
    public static int ComputeDynamicLimit(int baseLimit, IReadOnlyList<double> utilizationHistory)
    {
        if (utilizationHistory.Count == 0) return 0;
        var avgUtil = utilizationHistory.Average();
        if (avgUtil > 0.9)
            return (int)(baseLimit * 0.8);
        if (avgUtil > 0.7)
            return baseLimit;
        return (int)(baseLimit * 1.2);
    }

    public static (bool Accepted, string Reason) EvaluateAdmission(
        int currentDepth, int dynamicLimit, int priority, bool systemHealthy)
    {
        if (!systemHealthy && priority < Severity.High)
            return (false, "system unhealthy, low priority rejected");
        if (currentDepth >= dynamicLimit)
            return priority >= Severity.Critical
                ? (true, "admitted: critical priority override")
                : (false, $"queue full: {currentDepth}/{dynamicLimit}");
        return (true, "admitted");
    }

    public static IReadOnlyList<QueueItem> PriorityDrain(PriorityQueue queue, int minPriority)
    {
        var items = queue.Drain();
        return items.Where(i => i.Priority >= minPriority).ToList();
    }
}

public sealed class PolicyAwareQueue
{
    private readonly PolicyEngine _engine;
    private readonly PriorityQueue _queue;
    private readonly int _baseLimit;
    private readonly string _capturedPolicy;

    public PolicyAwareQueue(PolicyEngine engine, int baseLimit)
    {
        _engine = engine;
        _baseLimit = baseLimit;
        _capturedPolicy = engine.Current;
        _queue = new PriorityQueue(baseLimit);
    }

    public int EffectiveLimit
    {
        get
        {
            var mult = _capturedPolicy switch
            {
                "halted" => 0.0,
                "restricted" => 0.5,
                "watch" => 0.7,
                _ => 1.0,
            };
            return (int)(_baseLimit * mult);
        }
    }

    public (bool Admitted, string Reason) TryAdmit(QueueItem item)
    {
        var limit = EffectiveLimit;
        if (limit <= 0)
            return (false, "policy blocks all admissions");
        if (_queue.Size >= limit && item.Priority < Severity.Critical)
            return (false, $"limit {limit} reached");
        return _queue.Enqueue(item) ? (true, "admitted") : (false, "hard limit reached");
    }

    public QueueItem? Process() => _queue.Dequeue();
    public int Pending => _queue.Size;
    public string ActivePolicy => _capturedPolicy;
}

public sealed class BackpressureController
{
    private readonly int _hardLimit;
    private readonly double _processingRate;
    private readonly double _maxAcceptableWaitSeconds;
    private readonly List<(long Timestamp, int Depth)> _depthHistory = [];
    private readonly object _lock = new();

    public BackpressureController(int hardLimit, double processingRate, double maxAcceptableWaitSeconds)
    {
        _hardLimit = hardLimit;
        _processingRate = processingRate;
        _maxAcceptableWaitSeconds = maxAcceptableWaitSeconds;
    }

    public record BackpressureDecision(
        bool ShouldApply,
        double CurrentWaitEstimate,
        double Pressure,
        string Reason);

    public BackpressureDecision Evaluate(int currentDepth, long timestamp)
    {
        lock (_lock)
        {
            _depthHistory.Add((timestamp, currentDepth));
            if (_depthHistory.Count > 100)
                _depthHistory.RemoveAt(0);

            var waitEstimate = QueueGuard.EstimateWaitTime(currentDepth, _processingRate);
            var pressure = (double)currentDepth / _hardLimit;
            var health = QueueHealthMonitor.Check(currentDepth, _hardLimit);

            if (waitEstimate > _maxAcceptableWaitSeconds)
                return new BackpressureDecision(true, waitEstimate, pressure,
                    $"wait time {waitEstimate:F1}s exceeds max {_maxAcceptableWaitSeconds:F1}s");

            if (health.Status == "critical")
                return new BackpressureDecision(true, waitEstimate, pressure, "queue critical");

            if (health.Status == "warning" && IsDepthIncreasing())
                return new BackpressureDecision(true, waitEstimate, pressure, "queue growing under warning");

            return new BackpressureDecision(false, waitEstimate, pressure, "within limits");
        }
    }

    private bool IsDepthIncreasing()
    {
        if (_depthHistory.Count < 3) return false;
        var recent = _depthHistory.TakeLast(3).Select(h => h.Depth).ToList();
        return recent[2] > recent[1] && recent[1] > recent[0];
    }

    public double CurrentPressure(int depth) => (double)depth / _hardLimit;

    public IReadOnlyList<(long Timestamp, int Depth)> DepthHistory
    {
        get { lock (_lock) return _depthHistory.ToList(); }
    }
}

public sealed class AdmissionController
{
    private readonly BackpressureController _backpressure;
    private readonly PolicyAwareQueue _queue;
    private int _rejectedCount;
    private int _admittedCount;
    private readonly object _lock = new();

    public AdmissionController(BackpressureController backpressure, PolicyAwareQueue queue)
    {
        _backpressure = backpressure;
        _queue = queue;
    }

    public (bool Admitted, string Reason) Submit(QueueItem item, long timestamp)
    {
        lock (_lock)
        {
            var bp = _backpressure.Evaluate(_queue.Pending, timestamp);

            if (bp.ShouldApply && item.Priority < Severity.Critical)
            {
                _rejectedCount++;
                return (false, $"backpressure: {bp.Reason}");
            }

            var (admitted, reason) = _queue.TryAdmit(item);
            if (admitted) _admittedCount++;
            else _rejectedCount++;
            return (admitted, reason);
        }
    }

    public int RejectedCount { get { lock (_lock) return _rejectedCount; } }
    public int AdmittedCount { get { lock (_lock) return _admittedCount; } }
    public double RejectionRate
    {
        get
        {
            lock (_lock)
            {
                var total = _admittedCount + _rejectedCount;
                return total == 0 ? 0.0 : (double)_rejectedCount / total;
            }
        }
    }
}
