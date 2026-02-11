import unittest

from aetherops.statistics import percentile, rolling_sla, trimmed_mean


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


if __name__ == "__main__":
    unittest.main()
