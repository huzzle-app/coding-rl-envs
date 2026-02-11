import unittest

from heliosops.statistics import percentile


class StatisticsTests(unittest.TestCase):
    def test_percentile_returns_monotonic_rank(self) -> None:
        self.assertEqual(percentile([4, 1, 9, 7], 50), 4)
        self.assertEqual(percentile([], 95), 0)


if __name__ == "__main__":
    unittest.main()
