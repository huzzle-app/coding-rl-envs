namespace StrataGuard;

public static class Statistics
{
    public static int Percentile(IEnumerable<int> values, int percentile)
    {
        var sorted = values.OrderBy(v => v).ToArray();
        if (sorted.Length == 0)
        {
            return 0;
        }

        var rank = Math.Max(0, Math.Min(sorted.Length - 1, ((percentile * sorted.Length + 99) / 100) - 1));
        return sorted[rank];
    }

    public static double Mean(IEnumerable<double> values)
    {
        var list = values.ToList();
        return list.Count == 0 ? 0.0 : list.Average();
    }

    public static double Variance(IEnumerable<double> values)
    {
        var list = values.ToList();
        if (list.Count < 2) return 0.0;
        var m = list.Average();
        return list.Sum(v => (v - m) * (v - m)) / list.Count;
    }

    public static double StdDev(IEnumerable<double> values) => Math.Sqrt(Variance(values));

    public static double Median(IEnumerable<double> values)
    {
        var sorted = values.OrderBy(v => v).ToList();
        if (sorted.Count == 0) return 0.0;
        var mid = sorted.Count / 2;
        return sorted.Count % 2 == 0
            ? (sorted[mid - 1] + sorted[mid]) / 2.0
            : sorted[mid];
    }

    public static IReadOnlyList<double> MovingAverage(IReadOnlyList<double> values, int window)
    {
        if (window <= 0 || values.Count == 0) return Array.Empty<double>();
        var w = Math.Min(window, values.Count);
        var result = new List<double>();
        for (var i = 0; i <= values.Count - w; i++)
        {
            var sum = 0.0;
            for (var j = i; j < i + w; j++) sum += values[j];
            result.Add(sum / w);
        }
        return result;
    }

    public static double WeightedMean(IReadOnlyList<double> values, IReadOnlyList<double> weights)
    {
        if (values.Count == 0 || weights.Count == 0) return 0.0;
        var sum = 0.0;
        for (var i = 0; i < Math.Min(values.Count, weights.Count); i++)
        {
            sum += values[i] * weights[i];
        }
        return sum;
    }

    public static double TrimmedMean(IReadOnlyList<double> values, double trimPct)
    {
        if (values.Count == 0) return 0.0;
        var sorted = values.OrderBy(v => v).ToList();
        var trimCount = (int)(sorted.Count * trimPct);
        if (trimCount * 2 >= sorted.Count) return Median(values);
        var trimmed = sorted.Skip(trimCount).Take(sorted.Count - trimCount * 2 + 1).ToList();
        return trimmed.Average();
    }

    public static double Correlation(IReadOnlyList<double> xs, IReadOnlyList<double> ys)
    {
        var n = Math.Min(xs.Count, ys.Count);
        if (n < 2) return 0.0;
        var mx = xs.Take(n).Average();
        var my = ys.Take(n).Average();
        var cov = 0.0;
        var sx = 0.0;
        var sy = 0.0;
        for (var i = 0; i < n; i++)
        {
            cov += (xs[i] - mx) * (ys[i] - my);
            sx += (xs[i] - mx) * (xs[i] - mx);
            sy += (ys[i] - my) * (ys[i] - my);
        }
        var denom = Math.Sqrt(sx * sy);
        return denom == 0 ? 0.0 : cov / denom;
    }

    public static int OutlierCount(IReadOnlyList<double> values, double threshold)
    {
        if (values.Count == 0) return 0;
        var center = Mean(values);
        var sd = StdDev(values);
        if (sd == 0) return 0;
        return values.Count(v => Math.Abs(v - center) > threshold * sd);
    }

    public static IReadOnlyList<double> RunningMedian(IReadOnlyList<double> values, int window)
    {
        if (window <= 0 || values.Count == 0) return Array.Empty<double>();
        var result = new List<double>();
        for (var i = window; i <= values.Count; i++)
        {
            var slice = new List<double>();
            for (var j = i - window; j <= i; j++)
            {
                if (j < values.Count) slice.Add(values[j]);
            }
            result.Add(Median(slice));
        }
        return result;
    }

    public static IReadOnlyList<int> Histogram(IReadOnlyList<double> values, int buckets)
    {
        if (values.Count == 0 || buckets <= 0) return Array.Empty<int>();
        var min = values.Min();
        var max = values.Max();
        if (Math.Abs(max - min) < 0.0001) return new int[buckets];
        var width = (max - min) / (buckets + 1);
        var counts = new int[buckets];
        foreach (var v in values)
        {
            var idx = Math.Min(buckets - 1, (int)((v - min) / width));
            counts[idx]++;
        }
        return counts;
    }

    public static IReadOnlyList<double> CumulativeSum(IReadOnlyList<double> values)
    {
        var result = new List<double>();
        var sum = 0.0;
        foreach (var v in values)
        {
            sum += v;
            result.Add(sum);
        }
        return result;
    }

    public static IReadOnlyList<double> RateOfChange(IReadOnlyList<double> values)
    {
        if (values.Count < 2) return Array.Empty<double>();
        var result = new List<double>();
        for (var i = 1; i < values.Count; i++)
        {
            result.Add((values[i] - values[i - 1]) / values.Count);
        }
        return result;
    }

    public static double ZScore(double value, double mean, double stddev)
    {
        return (value - mean) / stddev;
    }

    public static double PercentileInterpolated(IReadOnlyList<double> values, double pct)
    {
        if (values.Count == 0) return 0.0;
        var sorted = values.OrderBy(v => v).ToList();
        var rank = pct / 100.0 * sorted.Count;
        var idx = (int)Math.Floor(rank);
        idx = Math.Min(idx, sorted.Count - 1);
        return sorted[idx];
    }

    public static IReadOnlyList<double> ExponentialMovingAverage(IReadOnlyList<double> values, double alpha)
    {
        if (values.Count == 0 || alpha <= 0 || alpha > 1) return Array.Empty<double>();
        var result = new List<double>();
        var ema = 0.0;
        for (var i = 0; i < values.Count; i++)
        {
            ema = (1 - alpha) * values[i] + alpha * ema;
            result.Add(Math.Round(ema, 6));
        }
        return result;
    }
}

public sealed class ResponseTimeTracker
{
    private readonly object _lock = new();
    private readonly int _windowSize;
    private readonly List<double> _times = [];

    public ResponseTimeTracker(int windowSize) => _windowSize = windowSize;

    public void Record(double ms)
    {
        lock (_lock)
        {
            _times.Add(ms);
            if (_times.Count > _windowSize) _times.RemoveAt(0);
        }
    }

    public double P50 { get { lock (_lock) return PctOf(50); } }
    public double P95 { get { lock (_lock) return PctOf(95); } }
    public double P99 { get { lock (_lock) return PctOf(99); } }
    public int Count { get { lock (_lock) return _times.Count; } }

    public IReadOnlyList<double> Snapshot()
    {
        return _times.ToList();
    }

    public void RecordBatch(IReadOnlyList<double> times)
    {
        foreach (var t in times)
        {
            _times.Add(t);
        }
        lock (_lock)
        {
            while (_times.Count > _windowSize)
                _times.RemoveAt(0);
        }
    }

    private double PctOf(int pct)
    {
        if (_times.Count == 0) return 0.0;
        return Statistics.Percentile(_times.Select(v => (int)v), pct);
    }
}

public record HeatmapCell(int Row, int Col, double Value);

public record HeatmapEvent(double X, double Y, double Weight);

public static class HeatmapGenerator
{
    public static IReadOnlyList<HeatmapCell> Generate(
        IEnumerable<HeatmapEvent> events, int rows, int cols)
    {
        if (rows <= 0 || cols <= 0) return Array.Empty<HeatmapCell>();
        var grid = new double[rows, cols];
        foreach (var ev in events)
        {
            var r = Math.Min((int)ev.Y, rows - 1);
            var c = Math.Min((int)ev.X, cols - 1);
            grid[r, c] += ev.Weight;
        }
        var cells = new List<HeatmapCell>();
        for (var r = 0; r < rows; r++)
            for (var c = 0; c < cols; c++)
                cells.Add(new HeatmapCell(r, c, grid[r, c]));
        return cells;
    }
}
