namespace AegisCore;

public static class Policy
{
    private static readonly string[] Order = ["normal", "watch", "restricted", "halted"];

    public static string NextPolicy(string current, int failureBurst)
    {
        var idx = Array.IndexOf(Order, current);
        idx = idx < 0 ? 0 : idx;
        
        if (failureBurst < 1)
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
        
        return successStreak > threshold;
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

    public string EscalateToLevel(string targetPolicy)
    {
        lock (_lock)
        {
            var policies = Policy.AllPolicies();
            var targetIdx = Array.IndexOf(policies, targetPolicy);
            if (targetIdx < 0) return _current;

            var currentIdx = Array.IndexOf(policies, _current);
            if (targetIdx <= currentIdx) return _current;

            _history.Add(new PolicyChange(_current, targetPolicy, $"direct escalation to {targetPolicy}"));
            _current = targetPolicy;
            return _current;
        }
    }

    public (string State, int TransitionCount) EscalateWithCount(int failureBurst, int rounds)
    {
        lock (_lock)
        {
            var count = 0;
            for (var i = 0; i < rounds; i++)
            {
                var next = Policy.NextPolicy(_current, failureBurst);
                if (next != _current)
                {
                    _history.Add(new PolicyChange(_current, next, $"escalation round {i}: {failureBurst} failures"));
                    _current = next;
                    count++;
                }
            }
            return (_current, count);
        }
    }
}

public static class RiskAssessment
{
    public static double ComputeRiskScore(string policyState, double failureRate, double slaCompliancePercent)
    {
        var stateIdx = Policy.PolicyIndex(policyState) ?? 0;
        var maxIdx = Policy.AllPolicies().Length - 1;
        var stateRisk = maxIdx > 0 ? (double)stateIdx / maxIdx : 0.0;
        var failureRisk = Math.Min(1.0, Math.Max(0.0, failureRate));
        var slaRisk = Math.Max(0.0, (100.0 - slaCompliancePercent) / 100.0);

        return stateRisk * 0.4 + failureRisk * 0.4 + slaRisk * 0.3;
    }

    public static string RecommendAction(double riskScore)
    {
        return riskScore switch
        {
            >= 0.8 => "halt_all_operations",
            >= 0.6 => "restrict_non_essential",
            >= 0.3 => "increase_monitoring",
            _ => "normal_operations",
        };
    }

    public static double AggregateRisk(IReadOnlyList<double> componentScores)
    {
        if (componentScores.Count == 0) return 0.0;
        var maxRisk = componentScores.Max();
        var avgRisk = componentScores.Average();
        return maxRisk * 0.7 + avgRisk * 0.3;
    }
}

public record SlaRecord(string ServiceId, long Timestamp, int ActualMinutes, int SlaMinutes);

public sealed class SlaTracker
{
    private readonly object _lock = new();
    private readonly long _windowDuration;
    private readonly List<SlaRecord> _records = [];
    private readonly Dictionary<string, double> _serviceComplianceCache = new();
    private long _lastEviction;

    public SlaTracker(long windowDuration)
    {
        _windowDuration = windowDuration;
    }

    public void Record(SlaRecord record)
    {
        lock (_lock)
        {
            _records.Add(record);
            _serviceComplianceCache.Remove(record.ServiceId);
        }
    }

    private void Evict(long now)
    {
        var cutoff = now - _windowDuration;
        _records.RemoveAll(r => r.Timestamp < cutoff);
        _serviceComplianceCache.Clear();
        _lastEviction = now;
    }

    public double GetServiceCompliance(string serviceId, long now)
    {
        lock (_lock)
        {
            Evict(now);

            if (_serviceComplianceCache.TryGetValue(serviceId, out var cached))
                return cached;

            var cutoff = now - _windowDuration;
            var records = _records.Where(r => r.ServiceId == serviceId && r.Timestamp <= now).ToList();
            if (records.Count == 0) return 100.0;

            var compliant = records.Count(r => r.ActualMinutes <= r.SlaMinutes);
            var compliance = (double)compliant / records.Count * 100.0;
            _serviceComplianceCache[serviceId] = compliance;
            return compliance;
        }
    }

    public double GetSystemCompliance(long now)
    {
        lock (_lock)
        {
            Evict(now);

            var serviceIds = _records.Select(r => r.ServiceId).Distinct().ToList();
            if (serviceIds.Count == 0) return 100.0;

            var totalRecords = 0;
            var totalCompliant = 0;

            foreach (var svcId in serviceIds)
            {
                var records = _records.Where(r => r.ServiceId == svcId).ToList();
                totalRecords += records.Count;
                totalCompliant += records.Count(r => r.ActualMinutes <= r.SlaMinutes);
            }

            return totalRecords == 0 ? 100.0 : (double)totalCompliant / totalRecords * 100.0;
        }
    }

    public string RecommendPolicyAction(long now)
    {
        var compliance = GetSystemCompliance(now);
        var riskScore = RiskAssessment.ComputeRiskScore("normal", 0.0, compliance);
        return RiskAssessment.RecommendAction(riskScore);
    }

    public int RecordCount { get { lock (_lock) return _records.Count; } }
}

public sealed class PolicyFeedbackLoop
{
    private readonly PolicyEngine _engine;
    private readonly SlaTracker _slaTracker;
    private int _consecutiveGoodWindows;
    private int _consecutiveBadWindows;

    public PolicyFeedbackLoop(PolicyEngine engine, SlaTracker slaTracker)
    {
        _engine = engine;
        _slaTracker = slaTracker;
    }

    public string Evaluate(long now, double escalationThreshold, double deescalationThreshold)
    {
        var compliance = _slaTracker.GetSystemCompliance(now);

        if (compliance < escalationThreshold)
        {
            _consecutiveBadWindows++;
            _consecutiveGoodWindows = 0;

            if (_consecutiveBadWindows >= 3)
                _engine.Escalate(_consecutiveBadWindows);
        }
        else if (compliance > deescalationThreshold)
        {
            _consecutiveGoodWindows++;
            _consecutiveBadWindows = 0;

            if (_consecutiveGoodWindows >= 5 && Policy.ShouldDeescalate(_consecutiveGoodWindows, _engine.Current))
                _engine.Deescalate();
        }
        else
        {
            _consecutiveGoodWindows = 0;
            _consecutiveBadWindows = 0;
        }

        return _engine.Current;
    }

    public int ConsecutiveGoodWindows => _consecutiveGoodWindows;
    public int ConsecutiveBadWindows => _consecutiveBadWindows;
}
