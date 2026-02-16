import unittest

from aetherops.statistics import (
    exponential_decay_mean,
    generate_heatmap,
    median,
    percentile,
    rolling_sla,
    trimmed_mean,
    variance,
)


class StatisticsTest(unittest.TestCase):
    def test_percentile(self) -> None:
        self.assertEqual(percentile([1, 2, 3, 4, 5], 50), 3.0)

    def test_trimmed_mean(self) -> None:
        self.assertAlmostEqual(trimmed_mean([1, 2, 3, 100], 0.25), 2.5)

    def test_trimmed_mean_invalid(self) -> None:
        with self.assertRaises(ValueError):
            trimmed_mean([1, 2], 0.6)

    def test_rolling_sla(self) -> None:
        self.assertEqual(rolling_sla([90, 100, 150], 120), 0.6667)


class StatisticsBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in statistics.py."""

    def test_variance_uses_bessel_correction(self) -> None:
        result = variance([2.0, 4.0])
        self.assertAlmostEqual(result, 2.0, places=3)

    def test_median_even_length_averages_middle(self) -> None:
        result = median([1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(result, 2.5, places=3)

    def test_generate_heatmap_fills_zero(self) -> None:
        grid = generate_heatmap(2, 2, [1.0, 2.0, 3.0])
        self.assertEqual(grid[1][1], 0.0)

    def test_exponential_decay_weights_recent(self) -> None:
        result = exponential_decay_mean([1.0, 1.0, 1.0, 1.0, 100.0], half_life=1)
        self.assertGreater(result, 50.0)


if __name__ == "__main__":
    unittest.main()
