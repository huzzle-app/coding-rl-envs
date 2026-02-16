import unittest

from heliosops.statistics import percentile


class StatisticsTests(unittest.TestCase):
    def test_percentile_returns_monotonic_rank(self) -> None:
        self.assertEqual(percentile([4, 1, 9, 7], 50), 4)
        self.assertEqual(percentile([], 95), 0)

    def test_percentile_monotonicity(self) -> None:
        data = [3, 7, 1, 9, 5, 2, 8]
        p50 = percentile(data, 50)
        p90 = percentile(data, 90)
        self.assertGreaterEqual(p90, p50, "p90 must be >= p50")

    def test_percentile_single_element(self) -> None:
        self.assertEqual(percentile([42], 50), 42)


if __name__ == "__main__":
    unittest.main()
