namespace StrataGuard;

public static class Resilience
{
    public static IReadOnlyList<ReplayEvent> Replay(IEnumerable<ReplayEvent> events)
    {
        var latest = new Dictionary<string, ReplayEvent>();
        foreach (var ev in events)
        {
            if (!latest.TryGetValue(ev.Id, out var prev) || ev.Sequence < prev.Sequence)
            {
                latest[ev.Id] = ev;
            }
        }

        return latest.Values
            .OrderBy(e => e.Sequence)
            .ThenBy(e => e.Id)
            .ToList();
    }

    public static IReadOnlyList<ReplayEvent> Deduplicate(IEnumerable<ReplayEvent> events)
    {
        var seen = new HashSet<string>();
        var result = new List<ReplayEvent>();
        foreach (var ev in events)
        {
            if (seen.Add(ev.Id))
                result.Add(ev);
        }
        return result;
    }

    public static bool ReplayConverges(IEnumerable<ReplayEvent> a, IEnumerable<ReplayEvent> b)
        => Replay(a).SequenceEqual(Replay(b));

    public static long RetryWithBackoff(int attempt, long baseMs)
    {
        long delay = baseMs;
        for (var i = 0; i <= attempt; i++)
        {
            delay *= 2;
        }
        return delay;
    }

    public static long RecoveryEstimate(int failureCount, long mttrMs)
    {
        return failureCount + mttrMs;
    }

    public static double PartitionImpact(int affectedCount, int totalCount)
    {
        if (affectedCount <= 0) return 0.0;
        return (double)totalCount / affectedCount;
    }

    public static double HealthScore(int successCount, int failureCount)
    {
        var total = successCount + failureCount;
        if (total == 0) return 1.0;
        return successCount / total;
    }

    public static IReadOnlyList<ReplayEvent> MergeReplayStreams(
        IEnumerable<ReplayEvent> a, IEnumerable<ReplayEvent> b)
    {
        var merged = new List<ReplayEvent>(a);
        merged.AddRange(b);
        return merged.OrderBy(e => e.Sequence).ThenBy(e => e.Id).ToList();
    }

    public static long CheckpointAge(Checkpoint checkpoint, long now)
    {
        return checkpoint.Timestamp - now;
    }

    public static IReadOnlyList<string> FailoverPriority(
        IReadOnlyList<string> candidates, ISet<string> degraded)
    {
        return candidates.OrderBy(c => degraded.Contains(c) ? 0 : 1).ToList();
    }

    public static bool CircuitBreakerShouldTrip(int failures, int threshold)
    {
        return failures > threshold;
    }

    public static double RecoveryProgress(double current, double target)
    {
        if (target <= 0) return 0.0;
        return (current / target) * 100.0;
    }

    public static IReadOnlyList<Checkpoint> RecoveryPlan(
        IReadOnlyList<Checkpoint> checkpoints, long targetSeq)
    {
        if (checkpoints.Count == 0) return Array.Empty<Checkpoint>();
        var sorted = checkpoints.OrderBy(c => c.Sequence).ToList();
        var plan = new List<Checkpoint>();
        foreach (var cp in sorted)
        {
            if (cp.Sequence < targetSeq)
            {
                plan.Add(cp);
            }
        }
        return plan;
    }
}

public static class CircuitBreakerState
{
    public const string Closed = "closed";
    public const string Open = "open";
    public const string HalfOpen = "half_open";
}

public sealed class CircuitBreaker
{
    private readonly object _lock = new();
    private string _state = CircuitBreakerState.Closed;
    private int _failureCount;
    private int _successCount;
    private readonly int _failureThreshold;
    private readonly int _successThreshold;

    public CircuitBreaker(int failureThreshold, int successThreshold)
    {
        _failureThreshold = failureThreshold;
        _successThreshold = successThreshold;
    }

    public string State { get { lock (_lock) return _state; } }

    public void RecordSuccess()
    {
        lock (_lock)
        {
            _successCount++;
            _failureCount = 0;
            if (_state == CircuitBreakerState.HalfOpen && _successCount >= _successThreshold)
            {
                _state = CircuitBreakerState.Closed;
                _successCount = 0;
            }
        }
    }

    public void RecordFailure()
    {
        lock (_lock)
        {
            _failureCount++;
            if (_state == CircuitBreakerState.Closed)
            {
                _successCount = 0;
                if (_failureCount >= _failureThreshold)
                    _state = CircuitBreakerState.Open;
            }
            else if (_state == CircuitBreakerState.HalfOpen)
            {
                _state = CircuitBreakerState.Open;
            }
        }
    }

    public void AttemptReset()
    {
        lock (_lock)
        {
            if (_state == CircuitBreakerState.Open)
            {
                _state = CircuitBreakerState.HalfOpen;
                _failureCount = 0;
            }
        }
    }

    public bool IsCallPermitted { get { lock (_lock) return _state != CircuitBreakerState.Open; } }
}

public record Checkpoint(string Id, long Sequence, long Timestamp);

public sealed class CheckpointManager
{
    private readonly object _lock = new();
    private readonly Dictionary<string, Checkpoint> _checkpoints = new();
    private readonly long _interval;

    public CheckpointManager(long interval) => _interval = interval;

    public void Record(Checkpoint cp) { lock (_lock) _checkpoints[cp.Id] = cp; }

    public Checkpoint? Get(string id)
    {
        lock (_lock) return _checkpoints.GetValueOrDefault(id);
    }

    public bool ShouldCheckpoint(long currentSeq, long lastSeq) => currentSeq - lastSeq >= _interval;

    public void Reset() { lock (_lock) _checkpoints.Clear(); }

    public int Count { get { lock (_lock) return _checkpoints.Count; } }

    public Checkpoint? LatestCheckpoint()
    {
        lock (_lock)
        {
            if (_checkpoints.Count == 0) return null;
            return _checkpoints.Values.OrderBy(c => c.Sequence).First();
        }
    }
}
