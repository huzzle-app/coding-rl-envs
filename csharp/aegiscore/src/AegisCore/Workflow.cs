namespace AegisCore;

public static class Workflow
{
    
    private static readonly Dictionary<string, HashSet<string>> Graph = new()
    {
        ["queued"] = ["allocated", "cancelled"],
        ["allocated"] = ["departed", "cancelled"],
        ["departed"] = ["arrived", "cancelled"],
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

    public IReadOnlyList<TransitionResult> BatchTransition(
        IReadOnlyList<(string EntityId, string To)> transitions, long timestamp)
    {
        var results = new List<TransitionResult>();
        lock (_lock)
        {
            foreach (var (entityId, to) in transitions)
            {
                if (!_entities.TryGetValue(entityId, out var from))
                {
                    results.Add(new TransitionResult(false, "", to, "entity not registered"));
                    continue;
                }
                if (!Workflow.CanTransition(from, to))
                {
                    results.Add(new TransitionResult(false, from, to, $"cannot transition from {from} to {to}"));
                    continue;
                }
                _entities[entityId] = to;
                _history.Add(new TransitionRecord(entityId, from, to, timestamp));
                results.Add(new TransitionResult(true, from, to, null));
            }
        }
        return results;
    }

    public TransitionResult TransitionIfState(string entityId, string expectedFrom, string to, long timestamp)
    {
        string? currentState;
        lock (_lock)
        {
            currentState = _entities.GetValueOrDefault(entityId);
        }

        if (currentState != expectedFrom)
            return new TransitionResult(false, currentState ?? "", to,
                $"expected state {expectedFrom} but was {currentState}");

        return Transition(entityId, to, timestamp);
    }
}

public static class WorkflowAnalyzer
{
    public static IReadOnlyList<string> FindDeadlockPaths(string from)
    {
        var deadEnds = new List<string>();
        var visited = new HashSet<string>();
        var stack = new Stack<string>();
        stack.Push(from);

        while (stack.Count > 0)
        {
            var state = stack.Pop();
            if (!visited.Add(state)) continue;
            var transitions = Workflow.AllowedTransitions(state);
            if (transitions.Count == 0 && !Workflow.IsTerminalState(state))
                deadEnds.Add(state);
            foreach (var next in transitions)
                stack.Push(next);
        }

        return deadEnds;
    }

    public static int ComputePathComplexity(string from, string to)
    {
        var path = Workflow.ShortestPath(from, to);
        if (path == null) return -1;
        var complexity = 0;
        for (var i = 0; i < path.Count - 1; i++)
        {
            complexity += Workflow.AllowedTransitions(path[i]).Count;
        }
        return complexity;
    }
}

public sealed class DispatchPipeline
{
    private readonly WorkflowEngine _workflow;
    private readonly PolicyEngine _policy;

    public DispatchPipeline(WorkflowEngine workflow, PolicyEngine policy)
    {
        _workflow = workflow;
        _policy = policy;
    }

    public record PipelineResult(
        bool Success,
        string? EntityId,
        string PolicyAtCheck,
        string? Error);

    public PipelineResult Execute(DispatchOrder order, Route route, long timestamp)
    {
        var policyState = _policy.Current;

        if (policyState == "halted")
            return new PipelineResult(false, null, policyState, "dispatch halted by policy");

        if (policyState == "restricted" && order.Urgency < Severity.High)
            return new PipelineResult(false, null, policyState, "restricted: low priority rejected");

        _workflow.Register(order.Id);

        var transition = _workflow.Transition(order.Id, "allocated", timestamp);
        if (!transition.Success)
            return new PipelineResult(false, order.Id, policyState, transition.Error);

        return new PipelineResult(true, order.Id, policyState, null);
    }

    public IReadOnlyList<PipelineResult> ExecuteBatch(
        IReadOnlyList<DispatchOrder> orders, Route route, long timestamp)
    {
        var results = new List<PipelineResult>();
        foreach (var order in orders)
            results.Add(Execute(order, route, timestamp));
        return results;
    }
}

public sealed class DispatchCoordinator
{
    private readonly WorkflowEngine _workflow;
    private readonly PolicyEngine _policy;
    private readonly LeaseManager _leases;
    private readonly CapacityPlanner _planner;
    private readonly object _lock = new();
    private readonly Dictionary<string, string> _orderToBerth = new();
    private readonly List<(string OrderId, long Timestamp, string Result)> _auditTrail = [];

    public DispatchCoordinator(
        WorkflowEngine workflow,
        PolicyEngine policy,
        LeaseManager leases,
        CapacityPlanner planner)
    {
        _workflow = workflow;
        _policy = policy;
        _leases = leases;
        _planner = planner;
    }

    public record CoordinationResult(
        bool Success,
        string OrderId,
        string? AssignedBerth,
        string PolicyState,
        string WorkflowState,
        string? Error);

    public CoordinationResult Dispatch(DispatchOrder order, long now, long leaseDuration)
    {
        lock (_lock)
        {
            var policyState = _policy.Current;

            if (policyState == "halted")
            {
                _auditTrail.Add((order.Id, now, "rejected:halted"));
                return new CoordinationResult(false, order.Id, null, policyState, "", "policy halted");
            }

            if (policyState == "restricted" && order.Urgency < Severity.High)
            {
                _auditTrail.Add((order.Id, now, "rejected:restricted"));
                return new CoordinationResult(false, order.Id, null, policyState, "", "restricted policy");
            }

            _workflow.Register(order.Id);

            var (assigned, berth) = _planner.TryAssign(order, now, leaseDuration);
            if (!assigned)
            {
                _auditTrail.Add((order.Id, now, "rejected:no_capacity"));
                return new CoordinationResult(false, order.Id, null, policyState,
                    _workflow.GetState(order.Id) ?? "", "no capacity");
            }

            var transition = _workflow.Transition(order.Id, "allocated", now);
            if (!transition.Success)
            {
                _leases.Release(berth!, order.Id);
                _auditTrail.Add((order.Id, now, $"rejected:transition_failed:{transition.Error}"));
                return new CoordinationResult(false, order.Id, berth, policyState,
                    _workflow.GetState(order.Id) ?? "", transition.Error);
            }

            _orderToBerth[order.Id] = berth!;
            _auditTrail.Add((order.Id, now, $"dispatched:berth={berth}"));
            return new CoordinationResult(true, order.Id, berth, policyState, "allocated", null);
        }
    }

    public IReadOnlyList<CoordinationResult> DispatchBatch(
        IReadOnlyList<DispatchOrder> orders, long now, long leaseDuration)
    {
        var results = new List<CoordinationResult>();
        foreach (var order in orders)
            results.Add(Dispatch(order, now, leaseDuration));
        return results;
    }

    public bool Complete(string orderId, long now)
    {
        lock (_lock)
        {
            var state = _workflow.GetState(orderId);
            if (state != "allocated") return false;

            var depResult = _workflow.Transition(orderId, "departed", now);
            if (!depResult.Success) return false;

            var arrResult = _workflow.Transition(orderId, "arrived", now + 1);
            if (!arrResult.Success) return false;

            if (_orderToBerth.TryGetValue(orderId, out var berth))
            {
                _leases.Release(berth, orderId);
                _orderToBerth.Remove(orderId);
            }

            return true;
        }
    }

    public string? GetAssignedBerth(string orderId)
    {
        lock (_lock) return _orderToBerth.GetValueOrDefault(orderId);
    }

    public IReadOnlyList<(string OrderId, long Timestamp, string Result)> AuditTrail
    {
        get { lock (_lock) return _auditTrail.ToList(); }
    }

    public int ActiveDispatches
    {
        get { lock (_lock) return _orderToBerth.Count; }
    }
}
