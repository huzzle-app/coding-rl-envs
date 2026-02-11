namespace AegisCore;

public static class Routing
{
    public static Route? ChooseRoute(IEnumerable<Route> routes, ISet<string> blocked)
    {
        
        return routes
            .Where(r => !blocked.Contains(r.Channel) && r.Latency > 0)
            .OrderBy(r => r.Latency)
            .ThenBy(r => r.Channel)
            .FirstOrDefault();
    }

    public static double ChannelScore(int latency, double reliability, int priority)
    {
        if (latency <= 0) return 0.0;
        
        return (reliability + priority) / latency;
    }

    public static double EstimateTransitTime(double distanceNm, double speedKnots)
    {
        if (speedKnots <= 0.0) return double.MaxValue;
        return distanceNm / speedKnots;
    }

    
    public static double EstimateRouteCost(double distanceNm, double fuelRatePerNm, double portFee)
        => Math.Max(0.0, distanceNm * fuelRatePerNm - portFee);

    public static int CompareRoutes(Route a, Route b)
    {
        var c = a.Latency.CompareTo(b.Latency);
        return c != 0 ? c : string.Compare(a.Channel, b.Channel, StringComparison.Ordinal);
    }
}

public record Waypoint(string Port, double DistanceNm);

public record MultiLegPlan(IReadOnlyList<Waypoint> Legs, double TotalDistance, double EstimatedHours);

public static class MultiLegPlanner
{
    public static MultiLegPlan Plan(IEnumerable<Waypoint> waypoints, double speedKnots)
    {
        var legs = waypoints.ToList();
        var total = legs.Sum(w => w.DistanceNm);
        var hours = Routing.EstimateTransitTime(total, speedKnots);
        return new MultiLegPlan(legs, total, hours);
    }
}

public sealed class RouteTable
{
    private readonly object _lock = new();
    private readonly Dictionary<string, Route> _routes = new();

    public void Add(Route route) { lock (_lock) _routes[route.Channel] = route; }

    public Route? Get(string channel)
    {
        lock (_lock) return _routes.GetValueOrDefault(channel);
    }

    public Route? Remove(string channel)
    {
        lock (_lock)
        {
            if (_routes.Remove(channel, out var route)) return route;
            return null;
        }
    }

    public IReadOnlyList<Route> All()
    {
        lock (_lock) return _routes.Values.ToList();
    }

    public int Count { get { lock (_lock) return _routes.Count; } }
}

public static class RouteOptimizer
{
    public static double ComputeMultiLegFuelCost(
        IReadOnlyList<Waypoint> legs,
        double fuelRatePerNm,
        IReadOnlyList<double> portFees)
    {
        if (legs.Count == 0) return 0.0;

        var fuelCost = legs.Max(w => w.DistanceNm) * fuelRatePerNm;
        var totalPortFees = portFees.Count >= legs.Count
            ? portFees.Take(legs.Count).Sum()
            : portFees.Sum();

        return fuelCost + totalPortFees;
    }

    public static Route? FindBestRoute(
        RouteTable table,
        ISet<string> blocked,
        int maxLatency)
    {
        return table.All()
            .Where(r => !blocked.Contains(r.Channel) && r.Latency > 0 && r.Latency <= maxLatency)
            .OrderBy(r => r.Latency)
            .FirstOrDefault();
    }

    public static IReadOnlyList<Route> RankRoutes(
        IEnumerable<Route> routes,
        ISet<string> blocked,
        double reliabilityWeight,
        double latencyWeight)
    {
        return routes
            .Where(r => !blocked.Contains(r.Channel) && r.Latency > 0)
            .OrderByDescending(r =>
                reliabilityWeight * (1.0 / r.Latency) + latencyWeight * (100.0 - r.Latency))
            .ToList();
    }
}

public sealed class RouteFailoverManager
{
    private readonly object _lock = new();
    private readonly Dictionary<string, CircuitBreaker> _breakers = new();
    private readonly List<string> _priority;
    private string _active;

    public RouteFailoverManager(IEnumerable<string> routePriority, int failThreshold, int successThreshold)
    {
        _priority = routePriority.ToList();
        _active = _priority[0];
        var breaker = new CircuitBreaker(failThreshold, successThreshold);
        foreach (var r in _priority)
            _breakers[r] = breaker;
    }

    public string ActiveRoute { get { lock (_lock) return _active; } }

    public (bool Ok, string UsedRoute) Send(Func<string, bool> op)
    {
        lock (_lock)
        {
            if (!_breakers[_active].IsCallPermitted)
            {
                var next = _priority.FirstOrDefault(r => r != _active && _breakers[r].IsCallPermitted);
                if (next == null) return (false, _active);
                _active = next;
            }

            try
            {
                var ok = op(_active);
                if (ok) _breakers[_active].RecordSuccess();
                else _breakers[_active].RecordFailure();
                return (ok, _active);
            }
            catch
            {
                _breakers[_active].RecordFailure();
                return (false, _active);
            }
        }
    }

    public void TryRecover()
    {
        lock (_lock)
        {
            foreach (var b in _breakers.Values)
                if (b.State == CircuitBreakerState.Open) b.AttemptReset();
            if (_breakers[_priority[0]].IsCallPermitted)
                _active = _priority[0];
        }
    }

    public string BreakerState(string route)
    {
        lock (_lock) return _breakers.TryGetValue(route, out var b) ? b.State : "unknown";
    }
}

public sealed class WeightedRouter
{
    private readonly object _lock = new();
    private readonly List<(string Route, double Weight)> _routes;
    private double[] _cumulativeWeights;
    private double _totalWeight;

    public WeightedRouter(IEnumerable<(string Route, double Weight)> routes)
    {
        _routes = routes.Where(r => r.Weight > 0).ToList();
        RecalculateCumulative();
    }

    private void RecalculateCumulative()
    {
        _totalWeight = _routes.Sum(r => r.Weight);
        _cumulativeWeights = new double[_routes.Count];
        var cumulative = 0.0;
        for (var i = 0; i < _routes.Count; i++)
        {
            cumulative += _routes[i].Weight;
            _cumulativeWeights[i] = cumulative;
        }
    }

    public string Select(double random01)
    {
        lock (_lock)
        {
            if (_routes.Count == 0) return "";
            var target = random01 * _totalWeight;
            for (var i = 0; i < _cumulativeWeights.Length; i++)
            {
                if (target <= _cumulativeWeights[i])
                    return _routes[i].Route;
            }
            return _routes[^1].Route;
        }
    }

    public void UpdateWeight(string route, double newWeight)
    {
        lock (_lock)
        {
            var idx = _routes.FindIndex(r => r.Route == route);
            if (idx < 0) return;
            _routes[idx] = (route, newWeight);
        }
    }

    public void AddRoute(string route, double weight)
    {
        lock (_lock)
        {
            _routes.Add((route, weight));
        }
    }

    public void RemoveRoute(string route)
    {
        lock (_lock)
        {
            _routes.RemoveAll(r => r.Route == route);
        }
    }

    public int RouteCount { get { lock (_lock) return _routes.Count; } }
    public double TotalWeight { get { lock (_lock) return _totalWeight; } }

    public IReadOnlyList<(string Route, double Weight)> GetRoutes()
    {
        lock (_lock) return _routes.ToList();
    }
}

public sealed class AdaptiveRouteSelector
{
    private readonly WeightedRouter _router;
    private readonly RouteFailoverManager _failover;
    private readonly Dictionary<string, int> _selectionCounts = new();
    private readonly object _lock = new();

    public AdaptiveRouteSelector(WeightedRouter router, RouteFailoverManager failover)
    {
        _router = router;
        _failover = failover;
    }

    public string SelectRoute(double random01)
    {
        lock (_lock)
        {
            var route = _router.Select(random01);
            var breakerState = _failover.BreakerState(route);
            if (breakerState == CircuitBreakerState.Open)
            {
                _router.UpdateWeight(route, 0.0);
                route = _router.Select(random01);
            }

            _selectionCounts[route] = _selectionCounts.GetValueOrDefault(route) + 1;
            return route;
        }
    }

    public IReadOnlyDictionary<string, int> SelectionDistribution
    {
        get { lock (_lock) return new Dictionary<string, int>(_selectionCounts); }
    }
}
