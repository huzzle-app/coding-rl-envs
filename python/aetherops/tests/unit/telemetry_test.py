import unittest

from aetherops.telemetry import anomaly_score, ewma, moving_average


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


if __name__ == "__main__":
    unittest.main()
