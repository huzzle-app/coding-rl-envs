import math
import unittest

from latticeforge.orbit import hohmann_delta_v


class HohmannDeltaVTest(unittest.TestCase):
    def test_leo_to_meo(self) -> None:
        dv = hohmann_delta_v(6771.0, 12771.0)
        self.assertGreater(dv, 1.5)
        self.assertLess(dv, 4.0)

    def test_leo_to_geo(self) -> None:
        dv = hohmann_delta_v(6571.0, 42164.0)
        self.assertAlmostEqual(dv, 3.9352, delta=0.05)

    def test_both_burns_included(self) -> None:
        r1, r2 = 6771.0, 6921.0
        dv = hohmann_delta_v(r1, r2)
        mu = 398600.4418
        a_t = (r1 + r2) / 2.0
        dv1 = abs(math.sqrt(mu * (2.0 / r1 - 1.0 / a_t)) - math.sqrt(mu / r1))
        dv2 = abs(math.sqrt(mu / r2) - math.sqrt(mu * (2.0 / r2 - 1.0 / a_t)))
        self.assertAlmostEqual(dv, dv1 + dv2, places=2)

    def test_symmetric_transfer(self) -> None:
        dv_up = hohmann_delta_v(7000.0, 8000.0)
        dv_down = hohmann_delta_v(8000.0, 7000.0)
        self.assertAlmostEqual(dv_up, dv_down, places=3)

    def test_same_orbit_zero(self) -> None:
        self.assertEqual(hohmann_delta_v(7000.0, 7000.0), 0.0)

    def test_invalid_radius(self) -> None:
        self.assertEqual(hohmann_delta_v(-100.0, 7000.0), 0.0)
        self.assertEqual(hohmann_delta_v(7000.0, 0.0), 0.0)

    def test_close_orbit_small_dv(self) -> None:
        dv = hohmann_delta_v(6771.0, 6871.0)
        self.assertGreater(dv, 0.0)
        self.assertLess(dv, 0.15)

    def test_large_ratio_transfer(self) -> None:
        dv = hohmann_delta_v(6571.0, 42164.0)
        mu = 398600.4418
        a_t = (6571.0 + 42164.0) / 2.0
        dv1 = abs(math.sqrt(mu * (2.0 / 6571.0 - 1.0 / a_t)) - math.sqrt(mu / 6571.0))
        dv2 = abs(math.sqrt(mu / 42164.0) - math.sqrt(mu * (2.0 / 42164.0 - 1.0 / a_t)))
        expected = round(dv1 + dv2, 4)
        self.assertAlmostEqual(dv, expected, places=2)


if __name__ == "__main__":
    unittest.main()
