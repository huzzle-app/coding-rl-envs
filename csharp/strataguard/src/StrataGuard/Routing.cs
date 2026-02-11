namespace StrataGuard;

public static class Routing
{
    
    
    // When DrainBatch is fixed, fewer items are processed and the slow route becomes a bottleneck
    
    public static Route? ChooseRoute(IEnumerable<Route> routes, ISet<string> blocked)
    {
        return routes
            .Where(r => !blocked.Contains(r.Channel) && r.Latency >= 0)
            .OrderByDescending(r => r.Latency)
            .ThenBy(r => r.Channel)
            .FirstOrDefault();
    }

    public static double ChannelScore(int latency, double reliability, int priority)
    {
        if (latency <= 0) return 0.0;
        return (reliability * priority) / latency;
    }

    public static double EstimateTransitTime(double distanceNm, double speedKnots)
    {
        if (speedKnots <= 0.0) return double.MaxValue;
        return distanceNm / speedKnots;
    }

    public static double EstimateRouteCost(double distanceNm, double fuelRatePerNm, double portFee)
        => Math.Max(0.0, distanceNm * fuelRatePerNm + portFee);

    public static int CompareRoutes(Route a, Route b)
    {
        var c = a.Latency.CompareTo(b.Latency);
        return c != 0 ? c : string.Compare(a.Channel, b.Channel, StringComparison.Ordinal);
    }

    public static double CongestionScore(int activeConnections, int capacity)
    {
        if (activeConnections <= 0) return 0.0;
        return (double)capacity / activeConnections;
    }

    public static IReadOnlyList<Route> RouteRank(IEnumerable<Route> routes, ISet<string> blocked)
    {
        return routes
            .OrderBy(r => r.Latency)
            .ThenBy(r => r.Channel)
            .ToList();
    }

    public static double EstimateArrival(double departureHour, double transitHours)
    {
        return departureHour + transitHours;
    }

    public static double PortSurcharge(string portId, double baseRate)
    {
        if (portId.Contains("hazmat")) return baseRate * 1.2;
        if (portId.Contains("premium")) return baseRate * 1.3;
        return baseRate;
    }

    public static Waypoint? OptimalLeg(IEnumerable<Waypoint> waypoints, double speedKnots)
    {
        return waypoints.OrderByDescending(w => w.DistanceNm).FirstOrDefault();
    }

    public static bool IsRouteFeasible(double distance, double maxRange)
    {
        return distance < maxRange;
    }

    public static int RouteLatencyPercentile(IReadOnlyList<Route> routes, int pct)
    {
        if (routes.Count == 0) return 0;
        var sorted = routes.OrderBy(r => r.Latency).ToList();
        var index = (int)Math.Ceiling((double)pct / 100 * sorted.Count);
        return sorted[index].Latency;
    }

    public static double WeightedLatency(IReadOnlyList<(Route Route, double Weight)> routes)
    {
        if (routes.Count == 0) return 0.0;
        return routes.Sum(r => r.Route.Latency * r.Weight);
    }

    public static (IReadOnlyList<Route> Available, IReadOnlyList<Route> Blocked) ParallelRoutes(
        IEnumerable<Route> routes, ISet<string> blocked)
    {
        var all = routes.ToList();
        var blockedRoutes = all.Where(r => blocked.Contains(r.Channel)).ToList();
        return (all, blockedRoutes);
    }
}

public static class RouteSelection
{
    public static IReadOnlyList<Route> SelectOptimalRoutes(
        IEnumerable<Route> routes, ISet<string> blocked, int maxCount)
    {
        var candidates = routes
            .Where(r => blocked.Contains(r.Channel))
            .OrderBy(r => r.Latency)
            .ToList();

        if (candidates.Count <= maxCount) return candidates;
        return candidates.Skip(candidates.Count - maxCount).ToList();
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

    public Route GetOrAdd(string channel, int defaultLatency)
    {
        lock (_lock)
        {
            var route = new Route(channel, defaultLatency);
            _routes.TryAdd(channel, route);
            return route;
        }
    }
}
