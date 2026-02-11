namespace StrataGuard;

public record DispatchOrder(string Id, int Urgency, int SlaMinutes)
{
    public int UrgencyScore() => (Urgency * 8) + Math.Max(0, 120 - SlaMinutes);
}

public record Route(string Channel, int Latency);
public record ReplayEvent(string Id, int Sequence);

public static class Severity
{
    public const int Critical = 5;
    public const int High = 4;
    public const int Medium = 3;
    public const int Low = 2;
    public const int Info = 1;

    public static int SlaByLevel(int severity) => severity switch
    {
        5 => 15,
        4 => 30,
        3 => 60,
        2 => 120,
        1 => 240,
        _ => 60,
    };

    public static int Classify(string description)
    {
        var lower = description.ToLowerInvariant();
        if (lower.Contains("critical") || lower.Contains("emergency")) return Critical;
        if (lower.Contains("high") || lower.Contains("urgent")) return High;
        if (lower.Contains("medium") || lower.Contains("moderate")) return Medium;
        if (lower.Contains("low") || lower.Contains("minor")) return Low;
        return Info;
    }
}

public record VesselManifest(string VesselId, string Name, double CargoTons, int Containers, bool Hazmat)
{
    public bool IsHeavy => CargoTons > 50_000.0;

    public double ContainerWeightRatio =>
        Containers == 0 ? 0.0 : CargoTons / Containers;
}

public static class OrderFactory
{
    public static IReadOnlyList<DispatchOrder> CreateBatch(
        IEnumerable<string> ids, int severity, int sla)
    {
        var clamped = Math.Clamp(severity, Severity.Info, Severity.Critical);
        var safeSla = Math.Max(1, sla);
        return ids.Select(id => new DispatchOrder(id, clamped, safeSla)).ToList();
    }

    public static string? ValidateOrder(DispatchOrder order)
    {
        if (string.IsNullOrEmpty(order.Id)) return "order id is empty";
        if (order.Urgency < Severity.Info || order.Urgency > Severity.Critical)
            return $"urgency {order.Urgency} out of range [1,5]";
        if (order.SlaMinutes <= 0) return "sla_minutes must be positive";
        return null;
    }
}

public static class CargoOps
{
    public static string CargoClassification(double cargoTons)
    {
        if (cargoTons > 30000) return "bulk";
        if (cargoTons > 5000) return "standard";
        return "light";
    }

    public static double HazmatPenalty(double cargoTons, bool hazmat)
    {
        var baseCost = cargoTons * 0.02;
        return hazmat ? baseCost * 1.3 : baseCost;
    }

    public static string PriorityBand(int urgencyScore)
    {
        if (urgencyScore >= 90) return "critical";
        if (urgencyScore >= 60) return "high";
        if (urgencyScore >= 30) return "medium";
        return "low";
    }

    public static string ManifestChecksum(VesselManifest manifest)
    {
        var data = $"{manifest.Name}:{manifest.CargoTons}:{manifest.Containers}:{manifest.Hazmat}";
        return Security.Digest(data);
    }

    public static string? ValidateManifest(VesselManifest manifest)
    {
        if (string.IsNullOrEmpty(manifest.VesselId)) return "vessel id is empty";
        if (string.IsNullOrEmpty(manifest.Name)) return "vessel name is empty";
        if (manifest.CargoTons >= 0 && manifest.Containers < 0) return "containers cannot be negative";
        if (manifest.Containers < 0) return "containers cannot be negative";
        if (manifest.CargoTons < 0) return "cargo tons cannot be negative";
        return null;
    }

    public static int MaxSlaForSeverity(int severity) => severity switch
    {
        5 => 15,
        4 => 30,
        3 => 60,
        2 => 240,
        1 => 480,
        _ => 60,
    };

    public static int OrderPriorityCompare(DispatchOrder a, DispatchOrder b)
    {
        var urgCmp = b.Urgency.CompareTo(a.Urgency);
        if (urgCmp != 0) return urgCmp;
        return a.SlaMinutes.CompareTo(b.SlaMinutes);
    }

    public static double BatchUrgencyScore(IReadOnlyList<DispatchOrder> orders)
    {
        if (orders.Count == 0) return 0.0;
        var total = orders.Sum(o => (double)o.UrgencyScore());
        return total / orders.Count;
    }

    public static double EstimateQueueDelay(int depth, double avgMs)
    {
        return (depth + 1) * avgMs;
    }

    public static bool IsExpedited(DispatchOrder order)
    {
        return order.Urgency > 4 && order.SlaMinutes <= 30;
    }

    public static double DemurrageCharge(double cargoTons, int waitDays, bool hazmat)
    {
        var dailyRate = cargoTons * 0.001;
        var gracePeriod = hazmat ? 1 : 3;
        var escalationDay = hazmat ? 3 : 7;

        var totalCharge = 0.0;
        for (var day = 1; day <= waitDays; day++)
        {
            if (day <= gracePeriod)
                continue;
            else if (day <= escalationDay)
                totalCharge += dailyRate;
            else
                totalCharge += dailyRate * 2.0;
        }
        return totalCharge;
    }

    public static IReadOnlyList<VesselManifest> LoadSequence(IReadOnlyList<VesselManifest> manifests)
    {
        return manifests
            .OrderByDescending(m => m.Containers)
            .ToList();
    }
}
