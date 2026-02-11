namespace AegisCore;

public record DispatchOrder(string Id, int Urgency, int SlaMinutes)
{
    
    public int UrgencyScore() => (Urgency * 10) - Math.Max(0, 120 - SlaMinutes);
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
    
    public bool IsHeavy => CargoTons >= 50_000.0;

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

public static class VesselOps
{
    public static double EstimateDockingTime(VesselManifest manifest, double baseHoursPerContainer)
    {
        var containerTime = manifest.Containers * baseHoursPerContainer;
        var cargoFactor = manifest.CargoTons > 25_000 ? 1.5 : 1.0;
        if (manifest.Hazmat)
            containerTime += manifest.Containers * baseHoursPerContainer;
        return containerTime * cargoFactor;
    }

    public static string ClassifyVessel(VesselManifest manifest)
    {
        if (manifest.CargoTons >= 100_000) return "ultra-large";
        if (manifest.CargoTons >= 50_000) return "large";
        if (manifest.CargoTons >= 10_000) return "medium";
        return "small";
    }

    public static bool RequiresEscort(VesselManifest manifest)
    {
        return manifest.Hazmat || manifest.CargoTons > 75_000 || manifest.Containers > 5000;
    }

    public static double CalculatePortDues(VesselManifest manifest, double ratePerTon, double hazmatSurcharge)
    {
        var baseDues = manifest.CargoTons * ratePerTon;
        if (manifest.Hazmat)
            baseDues = baseDues + hazmatSurcharge;
        return Math.Round(baseDues, 2);
    }
}
