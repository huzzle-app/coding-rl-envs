import unittest
from math import pi, sqrt

from services.orbit.service import (
    EARTH_MU,
    EARTH_RADIUS_KM,
    compute_orbital_period,
    predict_conjunction_risk,
    altitude_band,
)


class OrbitServiceTest(unittest.TestCase):
    def test_compute_orbital_period(self) -> None:
        alt = 400.0
        r = EARTH_RADIUS_KM + alt
        # T = 2 * pi * sqrt(r^3 / mu), must include factor of 2
        expected = round(2 * pi * sqrt(r ** 3 / EARTH_MU), 2)
        result = compute_orbital_period(alt)
        self.assertAlmostEqual(result, expected, places=1)

    def test_predict_conjunction_risk(self) -> None:
        # Low distance + high velocity = high risk
        risk = predict_conjunction_risk(distance_km=1.0, relative_velocity_kms=5.0)
        self.assertGreater(risk, 0.0)
        self.assertLessEqual(risk, 1.0)
        # Greater distance should lower risk
        risk_far = predict_conjunction_risk(distance_km=100.0, relative_velocity_kms=5.0)
        self.assertLess(risk_far, risk)

    def test_altitude_band_leo_boundary(self) -> None:
        # 1500 km should be LEO (upper bound is 2000, not 1000)
        self.assertEqual(altitude_band(1500.0), "LEO")
        self.assertEqual(altitude_band(500.0), "LEO")
        self.assertEqual(altitude_band(2500.0), "MEO")

    def test_altitude_band_geo(self) -> None:
        self.assertEqual(altitude_band(36000.0), "GEO")


if __name__ == "__main__":
    unittest.main()
