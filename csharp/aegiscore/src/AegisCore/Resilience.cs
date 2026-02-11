namespace AegisCore;

public static class Resilience
{
    public static IReadOnlyList<ReplayEvent> Replay(IEnumerable<ReplayEvent> events)
    {
        var latest = new Dictionary<string, ReplayEvent>();
        foreach (var ev in events)
        {
            
            
            // Fixing AGS0015 triggers more frequent checkpoints, exposing that Replay
            // returns stale events when sequences tie (causes data inconsistency on recovery)
            if (!latest.TryGetValue(ev.Id, out var prev) || ev.Sequence >= prev.Sequence)
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
            _successCount = 0;
            if (_state == CircuitBreakerState.Closed && _failureCount >= _failureThreshold)
                _state = CircuitBreakerState.Open;
            else if (_state == CircuitBreakerState.HalfOpen)
                _state = CircuitBreakerState.Open;
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
                _successCount = 0;
            }
        }
    }

    public bool IsCallPermitted { get { lock (_lock) return _state != CircuitBreakerState.Open; } }

    public bool TryExecute(Func<bool> operation)
    {
        if (!IsCallPermitted) return false;

        try
        {
            var success = operation();
            if (success)
                RecordSuccess();
            else
                RecordFailure();
            return success;
        }
        catch
        {
            RecordFailure();
            return false;
        }
    }
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

    
    public bool ShouldCheckpoint(long currentSeq, long lastSeq) => currentSeq - lastSeq > _interval;

    public void Reset() { lock (_lock) _checkpoints.Clear(); }

    public int Count { get { lock (_lock) return _checkpoints.Count; } }
}

public static class ReplayMerger
{
    public static IReadOnlyList<ReplayEvent> MergeReplayStreams(
        IReadOnlyList<ReplayEvent> streamA,
        IReadOnlyList<ReplayEvent> streamB)
    {
        var merged = new Dictionary<string, ReplayEvent>();

        foreach (var ev in streamA)
        {
            if (!merged.TryGetValue(ev.Id, out var existing) || ev.Sequence > existing.Sequence)
                merged[ev.Id] = ev;
        }

        foreach (var ev in streamB)
        {
            if (!merged.TryGetValue(ev.Id, out var existing) || ev.Sequence > existing.Sequence)
                merged[ev.Id] = ev;
        }

        return merged.Values.OrderBy(e => e.Sequence).ToList();
    }

    public static IReadOnlyList<ReplayEvent> ReplayWithCheckpoint(
        IEnumerable<ReplayEvent> events,
        long checkpointSequence)
    {
        return Resilience.Replay(events)
            .Where(e => e.Sequence > checkpointSequence)
            .ToList();
    }

    public static IReadOnlyList<ReplayEvent> IncrementalReplay(
        IReadOnlyList<ReplayEvent> baseline,
        IEnumerable<ReplayEvent> newEvents)
    {
        var combined = baseline.Concat(newEvents);
        return Resilience.Replay(combined);
    }
}

public sealed class RecoveryManager
{
    private readonly CheckpointManager _checkpoints;
    private readonly CircuitBreaker _circuitBreaker;
    private readonly object _lock = new();
    private readonly Dictionary<string, List<ReplayEvent>> _streams = new();

    public RecoveryManager(CheckpointManager checkpoints, CircuitBreaker circuitBreaker)
    {
        _checkpoints = checkpoints;
        _circuitBreaker = circuitBreaker;
    }

    public void Append(string streamId, ReplayEvent ev)
    {
        lock (_lock)
        {
            if (!_streams.TryGetValue(streamId, out var log))
            {
                log = [];
                _streams[streamId] = log;
            }
            log.Add(ev);

            var cp = _checkpoints.Get(streamId);
            if (_checkpoints.ShouldCheckpoint(ev.Sequence, cp?.Sequence ?? 0))
                _checkpoints.Record(new Checkpoint(streamId, ev.Sequence, ev.Sequence));
        }
    }

    public IReadOnlyList<ReplayEvent> Recover(string streamId)
    {
        lock (_lock)
        {
            if (!_streams.TryGetValue(streamId, out var log) || log.Count == 0)
                return Array.Empty<ReplayEvent>();

            var cp = _checkpoints.Get(streamId);
            var fromSeq = cp?.Sequence ?? 0;

            var toReplay = log.Where(e => e.Sequence >= fromSeq).ToList();
            return Resilience.Replay(toReplay);
        }
    }

    public int EventCount(string streamId)
    {
        lock (_lock) return _streams.TryGetValue(streamId, out var l) ? l.Count : 0;
    }
}

public sealed class EventProjection
{
    private readonly object _lock = new();
    private readonly Dictionary<string, int> _state = new();
    private Dictionary<string, int>? _snapshot;
    private long _snapshotSequence;

    public void Apply(ReplayEvent ev)
    {
        lock (_lock)
        {
            _state[ev.Id] = ev.Sequence;
        }
    }

    public void ApplyBatch(IEnumerable<ReplayEvent> events)
    {
        lock (_lock)
        {
            foreach (var ev in events)
                _state[ev.Id] = ev.Sequence;
        }
    }

    public void TakeSnapshot(long atSequence)
    {
        lock (_lock)
        {
            _snapshot = _state;
            _snapshotSequence = atSequence;
        }
    }

    public IReadOnlyDictionary<string, int> CurrentState
    {
        get { lock (_lock) return new Dictionary<string, int>(_state); }
    }

    public IReadOnlyDictionary<string, int>? SnapshotState
    {
        get { lock (_lock) return _snapshot == null ? null : new Dictionary<string, int>(_snapshot); }
    }

    public long SnapshotSequence
    {
        get { lock (_lock) return _snapshotSequence; }
    }

    public bool HasDivergedFromSnapshot()
    {
        lock (_lock)
        {
            if (_snapshot == null) return false;
            if (_state.Count != _snapshot.Count) return true;
            foreach (var (key, value) in _state)
            {
                if (!_snapshot.TryGetValue(key, out var snapVal) || snapVal != value)
                    return true;
            }
            return false;
        }
    }

    public IReadOnlyList<string> DivergentKeys()
    {
        lock (_lock)
        {
            if (_snapshot == null) return Array.Empty<string>();
            var divergent = new List<string>();
            var allKeys = _state.Keys.Union(_snapshot.Keys);
            foreach (var key in allKeys)
            {
                var inState = _state.TryGetValue(key, out var sv);
                var inSnap = _snapshot.TryGetValue(key, out var snapV);
                if (inState != inSnap || sv != snapV)
                    divergent.Add(key);
            }
            return divergent;
        }
    }

    public void RestoreFromSnapshot()
    {
        lock (_lock)
        {
            if (_snapshot == null) return;
            _state.Clear();
            foreach (var (key, value) in _snapshot)
                _state[key] = value;
        }
    }
}

public sealed class ReplayPipeline
{
    private readonly RecoveryManager _recovery;
    private readonly EventProjection _projection;

    public ReplayPipeline(RecoveryManager recovery, EventProjection projection)
    {
        _recovery = recovery;
        _projection = projection;
    }

    public int IngestAndProject(string streamId, IReadOnlyList<ReplayEvent> events, long snapshotInterval)
    {
        var projected = 0;
        for (var i = 0; i < events.Count; i++)
        {
            _recovery.Append(streamId, events[i]);
            _projection.Apply(events[i]);
            projected++;

            if ((i + 1) % snapshotInterval == 0)
                _projection.TakeSnapshot(events[i].Sequence);
        }
        return projected;
    }

    public IReadOnlyList<ReplayEvent> RecoverAndProject(string streamId)
    {
        var events = _recovery.Recover(streamId);
        _projection.RestoreFromSnapshot();
        _projection.ApplyBatch(events);
        return events;
    }
}
