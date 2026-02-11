namespace AegisCore;

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
        
        
        // Callers in Routing.cs (ChooseRoute) and Policy.cs (NextPolicy) cache URLs
        // and must be updated to re-fetch after the fix, otherwise stale URLs persist.
        // See also: RouteTable.Add() which stores Route objects with cached channel URLs.
        return def is null ? null : $"http://{def.Id}{def.HealthPath}";
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

public static class EndpointResolver
{
    public static string? ResolveEndpoint(string serviceId, string path)
    {
        var def = ServiceRegistry.All().FirstOrDefault(d => d.Id == serviceId);
        if (def is null) return null;
        return $"http://{def.Id}:{def.Port}{path}";
    }

    public static IReadOnlyList<string> ResolveDependencyChain(string serviceId)
    {
        var all = ServiceRegistry.All().ToDictionary(d => d.Id);
        if (!all.ContainsKey(serviceId)) return Array.Empty<string>();

        var chain = new List<string>();
        var visited = new HashSet<string>();
        var stack = new Stack<string>();
        stack.Push(serviceId);

        while (stack.Count > 0)
        {
            var current = stack.Pop();
            if (!visited.Add(current)) continue;
            chain.Add(current);
            if (all.TryGetValue(current, out var def))
            {
                foreach (var dep in def.Dependencies)
                    stack.Push(dep);
            }
        }

        return chain;
    }

    public static bool ValidateEndpointHealth(string serviceId)
    {
        var url = ResolveEndpoint(serviceId, "/health");
        return url != null && url.StartsWith("http://");
    }
}

public sealed class VersionTracker
{
    private readonly object _lock = new();
    private readonly Dictionary<string, Dictionary<string, int>> _vectors = new();

    public void Update(string entityId, string nodeId)
    {
        lock (_lock)
        {
            if (!_vectors.TryGetValue(entityId, out var vector))
            {
                vector = new Dictionary<string, int>();
                _vectors[entityId] = vector;
            }
            vector[nodeId] = vector.GetValueOrDefault(nodeId) + 1;
        }
    }

    public IReadOnlyDictionary<string, int>? GetVector(string entityId)
    {
        lock (_lock)
        {
            return _vectors.TryGetValue(entityId, out var v)
                ? new Dictionary<string, int>(v)
                : null;
        }
    }

    public string Compare(string entityA, string entityB)
    {
        lock (_lock)
        {
            var va = _vectors.GetValueOrDefault(entityA);
            var vb = _vectors.GetValueOrDefault(entityB);
            if (va == null || vb == null) return "unknown";

            var allKeys = va.Keys.Union(vb.Keys).ToList();
            var aGreater = false;
            var bGreater = false;

            foreach (var key in allKeys)
            {
                var a = va.GetValueOrDefault(key);
                var b = vb.GetValueOrDefault(key);
                if (a > b) aGreater = true;
                if (b > a) bGreater = true;
            }

            if (aGreater && !bGreater) return "a_dominates";
            if (bGreater && !aGreater) return "b_dominates";
            if (!aGreater && !bGreater) return "equal";
            return "concurrent";
        }
    }

    public Dictionary<string, int> Resolve(string entityA, string entityB)
    {
        lock (_lock)
        {
            var va = _vectors.GetValueOrDefault(entityA) ?? new Dictionary<string, int>();
            var vb = _vectors.GetValueOrDefault(entityB) ?? new Dictionary<string, int>();
            var allKeys = va.Keys.Union(vb.Keys);

            var resolved = new Dictionary<string, int>();
            foreach (var key in allKeys)
                resolved[key] = Math.Max(va.GetValueOrDefault(key), vb.GetValueOrDefault(key));

            return resolved;
        }
    }
}

public sealed class CascadingFailureDetector
{
    private readonly IReadOnlyList<ServiceDefinition> _services;

    public CascadingFailureDetector(IReadOnlyList<ServiceDefinition> services)
    {
        _services = services;
    }

    public double ComputeImpactScore(string failedServiceId)
    {
        var score = 0.0;
        var queue = new Queue<(string ServiceId, double Weight)>();
        queue.Enqueue((failedServiceId, 1.0));

        while (queue.Count > 0)
        {
            var (current, weight) = queue.Dequeue();
            var dependents = _services.Where(s => s.Dependencies.Contains(current)).ToList();

            foreach (var dep in dependents)
            {
                score += weight;
                queue.Enqueue((dep.Id, weight * 0.5));
            }
        }

        return score;
    }

    public IReadOnlyList<string> AffectedServices(string failedServiceId)
    {
        var affected = new List<string>();
        var queue = new Queue<string>();
        queue.Enqueue(failedServiceId);

        while (queue.Count > 0)
        {
            var current = queue.Dequeue();
            var dependents = _services.Where(s => s.Dependencies.Contains(current)).ToList();

            foreach (var dep in dependents)
            {
                affected.Add(dep.Id);
                queue.Enqueue(dep.Id);
            }
        }

        return affected;
    }

    public Dictionary<string, double> ComputeImpactMap(string failedServiceId)
    {
        var impacts = new Dictionary<string, double>();
        var queue = new Queue<(string ServiceId, double Weight)>();
        queue.Enqueue((failedServiceId, 1.0));

        while (queue.Count > 0)
        {
            var (current, weight) = queue.Dequeue();
            var dependents = _services.Where(s => s.Dependencies.Contains(current)).ToList();

            foreach (var dep in dependents)
            {
                impacts[dep.Id] = impacts.GetValueOrDefault(dep.Id) + weight;
                queue.Enqueue((dep.Id, weight * 0.5));
            }
        }

        return impacts;
    }
}

public sealed class ServiceHealthAggregator
{
    private readonly CascadingFailureDetector _detector;
    private readonly object _lock = new();
    private readonly Dictionary<string, bool> _healthStatus = new();

    public ServiceHealthAggregator(CascadingFailureDetector detector)
    {
        _detector = detector;
        foreach (var svc in ServiceRegistry.All())
            _healthStatus[svc.Id] = true;
    }

    public void MarkDown(string serviceId)
    {
        lock (_lock) _healthStatus[serviceId] = false;
    }

    public void MarkUp(string serviceId)
    {
        lock (_lock) _healthStatus[serviceId] = true;
    }

    public double SystemHealthScore()
    {
        lock (_lock)
        {
            var totalImpact = 0.0;
            var downServices = _healthStatus.Where(kv => !kv.Value).Select(kv => kv.Key).ToList();

            foreach (var svc in downServices)
                totalImpact += _detector.ComputeImpactScore(svc);

            var maxPossible = _healthStatus.Count;
            return maxPossible == 0 ? 1.0 : Math.Max(0.0, 1.0 - (totalImpact / maxPossible));
        }
    }

    public bool IsServiceHealthy(string serviceId)
    {
        lock (_lock) return _healthStatus.GetValueOrDefault(serviceId, false);
    }
}
