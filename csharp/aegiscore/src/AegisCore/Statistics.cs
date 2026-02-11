namespace AegisCore;

public static class Statistics
{
    public static int Percentile(IEnumerable<int> values, int percentile)
    {
        var sorted = values.OrderBy(v => v).ToArray();
        if (sorted.Length == 0)
        {
            return 0;
        }

        
        var rank = Math.Max(0, Math.Min(sorted.Length - 1, ((percentile * sorted.Length + 100) / 100) - 1));
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
        
        return list.Sum(v => (v - m) * (v - m)) / (list.Count - 1);
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

public static class AdvancedStatistics
{
    public static double WeightedPercentile(
        IReadOnlyList<double> values,
        IReadOnlyList<double> weights,
        int percentile)
    {
        if (values.Count == 0 || values.Count != weights.Count) return 0.0;

        var pairs = values.Zip(weights)
            .OrderBy(p => p.First)
            .ToList();

        var totalWeight = pairs.Sum(p => p.Second);
        if (totalWeight <= 0) return 0.0;

        var targetWeight = (percentile / 100.0) * totalWeight;
        var cumulative = 0.0;

        foreach (var (value, weight) in pairs)
        {
            cumulative += weight;
            if (cumulative >= targetWeight)
                return value;
        }

        return pairs.Last().First;
    }

    public static IReadOnlyList<double> ExponentialMovingAverage(
        IReadOnlyList<double> values, double alpha)
    {
        if (values.Count == 0 || alpha <= 0.0 || alpha > 1.0)
            return Array.Empty<double>();

        var result = new List<double> { values[0] };
        for (var i = 1; i < values.Count; i++)
        {
            var ema = alpha * values[i] + (1.0 - alpha) * values[i - 1];
            result.Add(ema);
        }

        return result;
    }

    public static double Covariance(IReadOnlyList<double> x, IReadOnlyList<double> y)
    {
        if (x.Count != y.Count || x.Count < 2) return 0.0;
        var meanX = x.Average();
        var meanY = y.Average();
        var sum = x.Zip(y).Sum(p => (p.First - meanX) * (p.Second - meanY));
        return sum / (x.Count - 1);
    }

    public static double Correlation(IReadOnlyList<double> x, IReadOnlyList<double> y)
    {
        var cov = Covariance(x, y);
        var stdX = Statistics.StdDev(x);
        var stdY = Statistics.StdDev(y);
        if (stdX == 0.0 || stdY == 0.0) return 0.0;
        return cov / (stdX * stdY);
    }
}

public sealed class AnomalyDetector
{
    private readonly double _threshold;
    private readonly int _windowSize;
    private readonly List<double> _observations = [];
    private readonly object _lock = new();

    public AnomalyDetector(double threshold, int windowSize)
    {
        _threshold = threshold;
        _windowSize = windowSize;
    }

    public (bool IsAnomaly, double ZScore) Evaluate(double value)
    {
        lock (_lock)
        {
            _observations.Add(value);
            if (_observations.Count > _windowSize)
                _observations.RemoveAt(0);

            if (_observations.Count < 3) return (false, 0.0);

            var mean = _observations.Average();
            var variance = _observations.Sum(x => (x - mean) * (x - mean)) / _observations.Count;
            var stdDev = Math.Sqrt(variance);

            if (stdDev < 1e-10) return (false, 0.0);

            var zScore = Math.Abs((value - mean) / stdDev);
            return (zScore > _threshold, zScore);
        }
    }

    public int ObservationCount { get { lock (_lock) return _observations.Count; } }
    public void Reset() { lock (_lock) _observations.Clear(); }
}

public sealed class TimeSeriesAggregator
{
    private readonly object _lock = new();
    private readonly long _bucketDuration;
    private readonly Dictionary<long, List<double>> _buckets = new();
    private double _runningSum;
    private int _runningCount;

    public TimeSeriesAggregator(long bucketDuration)
    {
        _bucketDuration = bucketDuration;
    }

    private long BucketKey(long timestamp) => timestamp / _bucketDuration;

    public void Add(long timestamp, double value)
    {
        lock (_lock)
        {
            var key = BucketKey(timestamp);
            if (!_buckets.TryGetValue(key, out var bucket))
            {
                bucket = [];
                _buckets[key] = bucket;
            }
            bucket.Add(value);
            _runningSum += value;
            _runningCount++;
        }
    }

    public double RunningMean
    {
        get { lock (_lock) return _runningCount == 0 ? 0.0 : _runningSum / _runningCount; }
    }

    public void EvictBefore(long timestamp)
    {
        lock (_lock)
        {
            var cutoffKey = BucketKey(timestamp);
            var toRemove = _buckets.Keys.Where(k => k < cutoffKey).ToList();
            foreach (var key in toRemove)
            {
                _buckets.Remove(key);
            }
        }
    }

    public double BucketMean(long timestamp)
    {
        lock (_lock)
        {
            var key = BucketKey(timestamp);
            if (!_buckets.TryGetValue(key, out var bucket) || bucket.Count == 0) return 0.0;
            return bucket.Average();
        }
    }

    public double WindowMean(long fromTimestamp, long toTimestamp)
    {
        lock (_lock)
        {
            var fromKey = BucketKey(fromTimestamp);
            var toKey = BucketKey(toTimestamp);
            var values = new List<double>();

            foreach (var (key, bucket) in _buckets)
            {
                if (key >= fromKey && key <= toKey)
                    values.AddRange(bucket);
            }

            return values.Count == 0 ? 0.0 : values.Average();
        }
    }

    public int BucketCount { get { lock (_lock) return _buckets.Count; } }
    public int TotalSamples { get { lock (_lock) return _runningCount; } }
}

public sealed class TrendDetector
{
    private readonly TimeSeriesAggregator _aggregator;
    private readonly AnomalyDetector _anomalyDetector;
    private readonly int _minDataPoints;

    public TrendDetector(TimeSeriesAggregator aggregator, AnomalyDetector anomalyDetector, int minDataPoints)
    {
        _aggregator = aggregator;
        _anomalyDetector = anomalyDetector;
        _minDataPoints = minDataPoints;
    }

    public record TrendResult(string Direction, double Slope, bool HasAnomaly, double AnomalyZScore);

    public TrendResult Analyze(IReadOnlyList<(long Timestamp, double Value)> recentPoints)
    {
        if (recentPoints.Count < _minDataPoints)
            return new TrendResult("insufficient_data", 0.0, false, 0.0);

        foreach (var (ts, val) in recentPoints)
            _aggregator.Add(ts, val);

        var n = recentPoints.Count;
        var sumX = 0.0;
        var sumY = 0.0;
        var sumXy = 0.0;
        var sumX2 = 0.0;

        for (var i = 0; i < n; i++)
        {
            double x = i;
            var y = recentPoints[i].Value;
            sumX += x;
            sumY += y;
            sumXy += x * y;
            sumX2 += x * x;
        }

        var denominator = n * sumX2 - sumX * sumX;
        var slope = denominator == 0 ? 0.0 : (n * sumXy - sumX * sumY) / denominator;

        var lastValue = recentPoints[^1].Value;
        var (isAnomaly, zScore) = _anomalyDetector.Evaluate(lastValue);

        var direction = slope switch
        {
            > 0.1 => "increasing",
            < -0.1 => "decreasing",
            _ => "stable",
        };

        return new TrendResult(direction, slope, isAnomaly, zScore);
    }
}
