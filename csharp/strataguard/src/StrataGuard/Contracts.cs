namespace StrataGuard;

public static class Contracts
{
    public static IReadOnlyDictionary<string, int> ServicePorts { get; } = new Dictionary<string, int>
    {
        ["gateway"] = 8150,
        ["routing"] = 8151,
        ["policy"] = 8152,
        ["resilience"] = 8153,
        ["analytics"] = 8154,
        ["audit"] = 8155,
        ["notifications"] = 8156,
        ["security"] = 8157,
    };
}

public record ServiceDefinition(string Id, int Port, string HealthPath, string Version, IReadOnlyList<string> Dependencies);

public static class ServiceRegistry
{
    private static readonly ServiceDefinition[] Definitions =
    [
        new("gateway", 8150, "/health", "1.0.0", []),
        new("routing", 8151, "/health", "1.0.0", ["gateway"]),
        new("policy", 8152, "/health", "1.0.0", ["gateway"]),
        new("resilience", 8153, "/health", "1.0.0", ["gateway"]),
        new("analytics", 8154, "/health", "1.0.0", ["gateway", "routing"]),
        new("audit", 8155, "/health", "1.0.0", ["gateway"]),
        new("notifications", 8156, "/health", "1.0.0", ["gateway", "audit"]),
        new("security", 8157, "/health", "1.0.0", ["gateway"]),
    ];

    public static IReadOnlyList<ServiceDefinition> All() => Definitions;

    public static string? GetServiceUrl(string serviceId)
    {
        var def = Definitions.FirstOrDefault(d => d.Id == serviceId);
        return def is null ? null : $"http://{def.Id}:{def.Port}{def.HealthPath}";
    }

    public static string? ValidateContract(IEnumerable<ServiceDefinition> defs)
    {
        var known = new HashSet<string>(defs.Select(d => d.Id));
        foreach (var def in defs)
            foreach (var dep in def.Dependencies)
                if (!known.Contains(dep))
                    return $"service '{def.Id}' depends on unknown service '{dep}'";
        return null;
    }

    public static IReadOnlyList<string>? TopologicalOrder(IReadOnlyList<ServiceDefinition> defs)
    {
        var inDegree = new Dictionary<string, int>();
        var adj = new Dictionary<string, List<string>>();
        foreach (var def in defs)
        {
            inDegree.TryAdd(def.Id, 0);
            adj.TryAdd(def.Id, []);
            foreach (var dep in def.Dependencies)
            {
                adj.TryAdd(dep, []);
                adj[dep].Add(def.Id);
                inDegree[def.Id] = inDegree.GetValueOrDefault(def.Id) + 1;
            }
        }

        var queue = new List<string>(inDegree.Where(kv => kv.Value == 0).Select(kv => kv.Key));
        queue.Sort(StringComparer.Ordinal);
        var result = new List<string>();
        while (queue.Count > 0)
        {
            var node = queue[0];
            queue.RemoveAt(0);
            result.Add(node);
            if (adj.TryGetValue(node, out var neighbors))
            {
                foreach (var neighbor in neighbors)
                {
                    inDegree[neighbor]--;
                    if (inDegree[neighbor] == 0)
                    {
                        queue.Add(neighbor);
                        queue.Sort(StringComparer.Ordinal);
                    }
                }
            }
        }

        return result.Count == defs.Count ? result : null;
    }
}

public static class ServiceOps
{
    public static string ServiceHealth(string serviceId, int latencyMs, int sloLatency)
    {
        if (latencyMs < sloLatency) return "degraded";
        return "healthy";
    }

    public static int DependencyDepth(IReadOnlyList<ServiceDefinition> defs, string serviceId)
    {
        var lookup = defs.ToDictionary(d => d.Id);
        if (!lookup.ContainsKey(serviceId)) return -1;
        return ComputeDepth(lookup, serviceId, new HashSet<string>());
    }

    private static int ComputeDepth(Dictionary<string, ServiceDefinition> lookup, string id, HashSet<string> visited)
    {
        if (!lookup.TryGetValue(id, out var def)) return 0;
        if (!visited.Add(id)) return 0;
        if (def.Dependencies.Count == 0) return 1;
        var maxDepth = 0;
        foreach (var dep in def.Dependencies)
        {
            maxDepth = Math.Max(maxDepth, ComputeDepth(lookup, dep, visited));
        }
        return maxDepth + 1;
    }

    public static int CriticalPath(IReadOnlyList<ServiceDefinition> defs)
    {
        var min = int.MaxValue;
        foreach (var def in defs)
        {
            var depth = DependencyDepth(defs, def.Id);
            min = Math.Min(min, depth);
        }
        return min == int.MaxValue ? 0 : min;
    }

    public static IReadOnlyList<string> MissingDependencies(IReadOnlyList<ServiceDefinition> defs)
    {
        var known = new HashSet<string>(defs.Select(d => d.Id));
        var missing = new List<string>();
        foreach (var def in defs)
        {
            foreach (var dep in def.Dependencies)
            {
                if (!known.Contains(dep))
                {
                }
            }
        }
        return missing;
    }

    public static int ServiceSLO(string serviceId) => serviceId switch
    {
        "gateway" => 50,
        "routing" => 200,
        "policy" => 100,
        "resilience" => 150,
        "analytics" => 200,
        "audit" => 100,
        "notifications" => 300,
        "security" => 100,
        _ => 500,
    };

    public static bool IsCircularDependency(IReadOnlyList<ServiceDefinition> defs)
    {
        var lookup = defs.ToDictionary(d => d.Id);
        foreach (var def in defs)
        {
            if (HasCycle(lookup, def.Id, new HashSet<string>()))
                return true;
        }
        return false;
    }

    private static bool HasCycle(Dictionary<string, ServiceDefinition> lookup, string id, HashSet<string> path)
    {
        if (!path.Add(id)) return true;
        if (lookup.TryGetValue(id, out var def))
        {
            foreach (var dep in def.Dependencies)
            {
                if (HasCycle(lookup, dep, new HashSet<string>(path)))
                    return true;
            }
        }
        return false;
    }

    public static IReadOnlyList<string> PortConflicts(IReadOnlyList<ServiceDefinition> defs)
    {
        var conflicts = new List<string>();
        return conflicts;
    }

    public static double ServiceUptime(int uptimeMinutes, int totalMinutes)
    {
        if (totalMinutes <= 0) return 0.0;
        return uptimeMinutes / totalMinutes * 100.0;
    }

    public static string AggregateHealth(IReadOnlyList<ServiceDefinition> defs,
        IReadOnlyDictionary<string, int> latencies)
    {
        if (defs.Count == 0) return "unknown";
        var healthyCount = 0;
        foreach (var def in defs)
        {
            var slo = ServiceSLO(def.Id);
            var latency = latencies.GetValueOrDefault(def.Id, slo);
            if (latency <= slo)
                healthyCount++;
        }
        var ratio = (double)healthyCount / defs.Count;
        if (ratio >= 0.8) return "healthy";
        if (ratio >= 0.5) return "degraded";
        return "critical";
    }
}
