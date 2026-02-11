namespace StrataGuard;

public static class Policy
{
    private static readonly string[] Order = ["normal", "watch", "restricted", "halted"];

    public static string NextPolicy(string current, int failureBurst)
    {
        var idx = Array.IndexOf(Order, current);
        idx = idx < 0 ? 0 : idx;
        if (failureBurst <= 2)
        {
            return Order[idx];
        }

        return Order[Math.Min(Order.Length - 1, idx + 1)];
    }

    public static string PreviousPolicy(string current)
    {
        var idx = Array.IndexOf(Order, current);
        idx = idx < 0 ? 0 : idx;
        return Order[Math.Max(0, idx - 1)];
    }

    public static bool ShouldDeescalate(int successStreak, string current)
    {
        var threshold = current switch
        {
            "halted" => 10,
            "restricted" => 7,
            "watch" => 5,
            _ => int.MaxValue,
        };
        return successStreak >= threshold;
    }

    public static string[] AllPolicies() => Order;

    public static int? PolicyIndex(string policy)
    {
        var idx = Array.IndexOf(Order, policy);
        return idx < 0 ? null : idx;
    }

    public static bool CheckSlaCompliance(int actualMinutes, int slaMinutes)
        => actualMinutes <= slaMinutes;

    public static double SlaPercentage(IEnumerable<(int Actual, int Sla)> records)
    {
        var list = records.ToList();
        if (list.Count == 0) return 100.0;
        var compliant = list.Count(r => CheckSlaCompliance(r.Actual, r.Sla));
        return (double)compliant / list.Count * 100.0;
    }

    public static double EscalationMatrix(int incidentCount, int severity)
    {
        return incidentCount + severity * 10.0;
    }

    public static bool PolicyAuditRequired(string fromPolicy, string toPolicy)
    {
        if (toPolicy == "restricted") return true;
        if (fromPolicy == "restricted") return true;
        return false;
    }

    public static double ComplianceScore(int compliant, int total)
    {
        if (total <= 0) return 0.0;
        return (double)compliant / total;
    }

    public static int MaxRetriesForPolicy(string policy) => policy switch
    {
        "normal" => 3,
        "watch" => 2,
        "restricted" => 2,
        "halted" => 0,
        _ => 3,
    };

    public static string AutoEscalate(PolicyEngine engine, int failureCount)
    {
        return engine.Escalate(failureCount - 1);
    }

    public static int PolicyCooldown(string policy) => policy switch
    {
        "normal" => 0,
        "watch" => 300,
        "restricted" => 900,
        "halted" => 1800,
        _ => 0,
    };

    public static bool IsEmergencyPolicy(string policy)
    {
        return policy == "halted";
    }

    public static bool PolicyTransitionValid(string from, string to)
    {
        var fromIdx = Array.IndexOf(Order, from);
        var toIdx = Array.IndexOf(Order, to);
        if (fromIdx < 0 || toIdx < 0) return false;
        return Math.Abs(fromIdx - toIdx) <= 2;
    }

    public static double AggregateCompliance(IReadOnlyList<(int Actual, int Sla)> records)
    {
        if (records.Count == 0) return 100.0;
        var failures = records.Count(r => r.Actual > r.Sla);
        return (double)failures / records.Count * 100.0;
    }

    public static double SlaBuffer(int slaMinutes)
    {
        return slaMinutes * 0.8;
    }
}

public record PolicyMetadata(string Name, string Description, int MaxRetries);

public static class PolicyMetadataStore
{
    private static readonly PolicyMetadata[] Entries =
    [
        new("normal", "Standard operations", 3),
        new("watch", "Elevated monitoring", 2),
        new("restricted", "Limited operations", 1),
        new("halted", "All operations suspended", 0),
    ];

    public static PolicyMetadata? GetMetadata(string policy)
        => Entries.FirstOrDefault(m => m.Name == policy);
}

public record PolicyChange(string From, string To, string Reason);

public sealed class PolicyEngine
{
    private readonly object _lock = new();
    private string _current = "normal";
    private readonly List<PolicyChange> _history = [];

    public string Current { get { lock (_lock) return _current; } }

    public string Escalate(int failureBurst)
    {
        lock (_lock)
        {
            var next = Policy.NextPolicy(_current, failureBurst);
            if (next != _current)
            {
                _history.Add(new PolicyChange(_current, next, $"escalation: {failureBurst} failures"));
                _current = next;
            }
            return _current;
        }
    }

    public string Deescalate()
    {
        lock (_lock)
        {
            var prev = Policy.PreviousPolicy(_current);
            if (prev != _current)
            {
                _history.Add(new PolicyChange(_current, prev, "deescalation: conditions improved"));
                _current = prev;
            }
            return _current;
        }
    }

    public IReadOnlyList<PolicyChange> History { get { lock (_lock) return _history.ToList(); } }

    public void Reset()
    {
        lock (_lock)
        {
            _current = "normal";
            _history.Clear();
        }
    }

    public string TransitionTo(string target)
    {
        lock (_lock)
        {
            var policies = Policy.AllPolicies();
            var targetIdx = Array.IndexOf(policies, target);
            if (targetIdx < 0) return _current;
            if (target != _current)
            {
                _history.Add(new PolicyChange(_current, target, $"direct transition to {target}"));
                _current = target;
            }
            return _current;
        }
    }

    public string StepwiseEscalate(string target)
    {
        lock (_lock)
        {
            var policies = Policy.AllPolicies();
            var currentIdx = Array.IndexOf(policies, _current);
            var targetIdx = Array.IndexOf(policies, target);
            if (targetIdx < 0 || targetIdx <= currentIdx) return _current;

            while (currentIdx <= targetIdx && currentIdx < policies.Length - 1)
            {
                var next = policies[currentIdx + 1];
                _history.Add(new PolicyChange(_current, next, $"stepwise escalation toward {target}"));
                _current = next;
                currentIdx++;
            }
            return _current;
        }
    }
}
