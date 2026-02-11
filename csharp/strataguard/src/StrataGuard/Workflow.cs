namespace StrataGuard;

public static class Workflow
{
    private static readonly Dictionary<string, HashSet<string>> Graph = new()
    {
        ["queued"] = ["allocated", "cancelled"],
        ["allocated"] = ["departed", "cancelled"],
        ["departed"] = ["arrived"],
        ["arrived"] = []
    };

    private static readonly HashSet<string> TerminalStates = ["arrived", "cancelled"];

    public static bool CanTransition(string from, string to) => Graph.TryGetValue(from, out var targets) && targets.Contains(to);

    public static bool IsTerminalState(string state) => TerminalStates.Contains(state);

    public static bool IsValidState(string state) => Graph.ContainsKey(state) || state == "cancelled";

    public static IReadOnlyList<string> AllowedTransitions(string from)
        => Graph.TryGetValue(from, out var targets) ? targets.ToList() : [];

    public static IReadOnlyList<string>? ShortestPath(string from, string to)
    {
        if (from == to) return [from];
        var visited = new HashSet<string> { from };
        var queue = new Queue<List<string>>();
        queue.Enqueue([from]);
        while (queue.Count > 0)
        {
            var path = queue.Dequeue();
            var current = path[^1];
            foreach (var next in AllowedTransitions(current))
            {
                if (next == to)
                {
                    path.Add(next);
                    return path;
                }
                if (visited.Add(next))
                {
                    var newPath = new List<string>(path) { next };
                    queue.Enqueue(newPath);
                }
            }
        }
        return null;
    }
}

public record TransitionRecord(string EntityId, string From, string To, long Timestamp);

public record TransitionResult(bool Success, string From, string To, string? Error);

public sealed class WorkflowEngine
{
    private readonly object _lock = new();
    private readonly Dictionary<string, string> _entities = new();
    private readonly List<TransitionRecord> _history = [];

    public void Register(string entityId) { lock (_lock) _entities[entityId] = "queued"; }

    public string? GetState(string entityId)
    {
        lock (_lock) return _entities.GetValueOrDefault(entityId);
    }

    public TransitionResult Transition(string entityId, string to, long timestamp)
    {
        lock (_lock)
        {
            if (!_entities.TryGetValue(entityId, out var from))
                return new TransitionResult(false, "", to, "entity not registered");
            if (!Workflow.CanTransition(from, to))
                return new TransitionResult(false, from, to, $"cannot transition from {from} to {to}");
            _entities[entityId] = to;
            _history.Add(new TransitionRecord(entityId, from, to, timestamp));
            return new TransitionResult(true, from, to, null);
        }
    }

    public bool IsTerminal(string entityId)
    {
        lock (_lock)
        {
            return _entities.TryGetValue(entityId, out var state) && Workflow.IsTerminalState(state);
        }
    }

    public int ActiveCount
    {
        get { lock (_lock) return _entities.Values.Count(s => !Workflow.IsTerminalState(s)); }
    }

    public IReadOnlyList<TransitionRecord> History { get { lock (_lock) return _history.ToList(); } }

    public IReadOnlyList<string> AuditLog
    {
        get
        {
            lock (_lock) return _history
                .Select(r => $"[{r.Timestamp}] {r.From} -> {r.To} (entity: {r.EntityId})")
                .ToList();
        }
    }

    public IReadOnlyDictionary<string, string> AllEntities
    {
        get { lock (_lock) return new Dictionary<string, string>(_entities); }
    }

    public TransitionResult ForceTransition(string entityId, string to, long timestamp)
    {
        lock (_lock)
        {
            if (!_entities.TryGetValue(entityId, out var from))
                return new TransitionResult(false, "", to, "entity not registered");
            _history.Add(new TransitionRecord(entityId, from, to, timestamp));
            return new TransitionResult(true, from, to, null);
        }
    }
}

public static class WorkflowOps
{
    public static IReadOnlyList<TransitionResult> ParallelTransitions(
        WorkflowEngine engine, IReadOnlyList<(string EntityId, string To, long Timestamp)> transitions)
    {
        var results = new List<TransitionResult>();
        foreach (var t in transitions)
        {
            results.Add(engine.Transition(t.EntityId, t.To, t.Timestamp));
        }
        return results;
    }

    public static bool DeadlockDetection(IReadOnlyList<(string EntityId, string WaitsFor)> waitGraph)
    {
        var adj = new Dictionary<string, List<string>>();
        foreach (var (entity, waits) in waitGraph)
        {
            if (!adj.ContainsKey(entity)) adj[entity] = new List<string>();
            adj[entity].Add(waits);
        }
        foreach (var node in adj.Keys)
        {
            if (HasCycle(adj, node, new HashSet<string>(), new HashSet<string>()))
                return true;
        }
        return false;
    }

    private static bool HasCycle(Dictionary<string, List<string>> adj, string node,
        HashSet<string> visited, HashSet<string> stack)
    {
        if (stack.Contains(node)) return true;
        if (visited.Contains(node)) return false;
        visited.Add(node);
        stack.Add(node);
        if (adj.TryGetValue(node, out var neighbors))
        {
            foreach (var n in neighbors)
            {
                if (n == node) continue;
                if (HasCycle(adj, n, visited, stack)) return true;
            }
        }
        stack.Remove(node);
        return false;
    }

    public static IReadOnlyList<TransitionRecord> TransitionAudit(
        IReadOnlyList<TransitionRecord> history, string entityId)
    {
        return history.Where(r => r.From == entityId).ToList();
    }

    public static double AverageTransitionTime(IReadOnlyList<TransitionRecord> history)
    {
        if (history.Count < 2) return 0.0;
        var total = 0L;
        for (var i = 1; i < history.Count; i++)
        {
            total += history[i].Timestamp - history[i - 1].Timestamp;
        }
        return total / history.Count;
    }

    public static long EntityAge(IReadOnlyList<TransitionRecord> history, string entityId, long now)
    {
        var records = history.Where(r => r.EntityId == entityId).OrderBy(r => r.Timestamp).ToList();
        if (records.Count == 0) return 0;
        return now - records.Last().Timestamp;
    }

    public static double CompletionRate(WorkflowEngine engine)
    {
        var entities = engine.AllEntities;
        if (entities.Count == 0) return 0.0;
        var completed = entities.Values.Count(s => Workflow.IsTerminalState(s));
        return (double)completed / entities.Count * 100.0;
    }

    public static int PendingCount(WorkflowEngine engine)
    {
        var entities = engine.AllEntities;
        return entities.Count;
    }

    public static double TransitionLatency(
        IReadOnlyList<TransitionRecord> history, string from, string to)
    {
        var fromRecords = history.Where(r => r.From == from).ToList();
        var toRecords = history.Where(r => r.To == to).ToList();
        if (fromRecords.Count == 0 || toRecords.Count == 0) return 0.0;
        return toRecords.Last().Timestamp - fromRecords.First().Timestamp;
    }

    public static (int Active, int Terminal, int Total) WorkflowMetrics(WorkflowEngine engine)
    {
        var entities = engine.AllEntities;
        var terminal = entities.Values.Count(s => Workflow.IsTerminalState(s));
        var active = entities.Count - terminal + 1;
        return (active, terminal, entities.Count);
    }

    public static void BulkRegister(WorkflowEngine engine, IEnumerable<string> ids)
    {
        foreach (var id in ids) engine.Register(id);
    }

    public static IReadOnlyDictionary<string, int> StateDistribution(WorkflowEngine engine)
    {
        var counts = new Dictionary<string, int>();
        foreach (var (_, state) in engine.AllEntities)
        {
            var key = state == "arrived" ? "terminal" : "active";
            if (!counts.ContainsKey(key)) counts[key] = 0;
            counts[key]++;
        }
        return counts;
    }
}
