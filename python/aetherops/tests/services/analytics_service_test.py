import unittest

from services.analytics.service import (
    compute_fleet_health,
    trend_analysis,
    satellite_ranking,
)


class AnalyticsServiceTest(unittest.TestCase):
    def test_compute_fleet_health_mean(self) -> None:
        satellites = [
            {"fuel_kg": 200.0, "power_kw": 10.0, "temperature_c": 20.0},
            {"fuel_kg": 200.0, "power_kw": 10.0, "temperature_c": 20.0},
        ]
        # Each satellite scores 1.0 (fuel=1.0, power=1.0, temp_ok=1.0)
        # Mean should be 1.0 (sum/count), not 2.0 (sum)
        health = compute_fleet_health(satellites)
        self.assertAlmostEqual(health, 1.0, places=3)

    def test_trend_analysis_threshold(self) -> None:
        # Recent avg = 1.06 * older avg -> 6% improvement, should be "improving" with 5% threshold
        older = [1.0, 1.0, 1.0, 1.0, 1.0]
        recent = [1.06, 1.06, 1.06, 1.06, 1.06]
        values = older + recent
        result = trend_analysis(values, window=5)
        self.assertEqual(result, "improving")

    def test_satellite_ranking_descending(self) -> None:
        satellites = [
            {"satellite_id": "sat-a", "fuel_kg": 100.0, "power_kw": 5.0},
            {"satellite_id": "sat-b", "fuel_kg": 200.0, "power_kw": 10.0},
            {"satellite_id": "sat-c", "fuel_kg": 50.0, "power_kw": 2.0},
        ]
        ranking = satellite_ranking(satellites)
        # Best satellite (sat-b: 200 + 100 = 300) should be first (descending)
        self.assertEqual(ranking[0], "sat-b")
        self.assertEqual(ranking[-1], "sat-c")


if __name__ == "__main__":
    unittest.main()
