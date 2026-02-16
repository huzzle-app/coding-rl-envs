import math
import unittest

from aetherops.telemetry import (
    adaptive_threshold,
    anomaly_score,
    correlate_streams,
    detect_drift,
    downsample,
    ewma,
    moving_average,
    zscore_outliers,
)


class TelemetryTest(unittest.TestCase):
    def test_moving_average(self) -> None:
        out = moving_average([1, 2, 3, 4], 2)
        self.assertEqual(out, [1.0, 1.5, 2.5, 3.5])

    def test_ewma(self) -> None:
        out = ewma([10.0, 12.0, 11.0], 0.5)
        self.assertEqual(out, [10.0, 11.0, 11.0])

    def test_anomaly_score(self) -> None:
        score = anomaly_score([105, 95, 110], baseline=100, tolerance=10)
        self.assertAlmostEqual(score, 0.6667, places=3)

    def test_ewma_invalid_alpha(self) -> None:
        with self.assertRaises(ValueError):
            ewma([1, 2], 0)


class TelemetryBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in telemetry.py."""

    def test_zscore_outliers_returns_outliers(self) -> None:
        values = [10.0] * 99 + [1000.0]
        outliers = zscore_outliers(values, z_limit=3.0)
        self.assertIn(1000.0, outliers)
        self.assertLess(len(outliers), 50)

    def test_downsample_averages_buckets(self) -> None:
        result = downsample([1.0, 3.0, 5.0, 7.0], factor=2)
        self.assertEqual(result, [2.0, 6.0])

    def test_adaptive_threshold_linear_sensitivity(self) -> None:
        values = list(range(1, 21))
        result = adaptive_threshold(values, sensitivity=2.0, min_samples=20)
        baseline = sum(values) / 20
        var = sum((v - baseline) ** 2 for v in values) / 20
        std = math.sqrt(var)
        expected = baseline + 2.0 * std
        self.assertAlmostEqual(result["threshold"], expected, places=2)

    def test_detect_drift_boundary_not_flagged(self) -> None:
        """Value at exactly threshold z-score should not be flagged (> not >=)."""
        values = [0.0, 0.0, 0.0, 0.0, 4.0]
        result = detect_drift(values, threshold=2.0)
        self.assertEqual(result, [])

    def test_correlate_streams_uses_last_element(self) -> None:
        """Correlation must consider the last element of stream_b."""
        a = [0.0, 0.0, 1.0]
        b = [0.0, 0.0, 1.0]
        result = correlate_streams(a, b, max_lag=1)
        self.assertGreater(result["correlation"], 0.0)


if __name__ == "__main__":
    unittest.main()
