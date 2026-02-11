import unittest

from latticeforge.policy import compound_risk_assessment


class CompoundRiskAssessmentTest(unittest.TestCase):
    def test_empty_factors(self) -> None:
        self.assertAlmostEqual(compound_risk_assessment([]), 10.0)

    def test_single_small_factor(self) -> None:
        risk = compound_risk_assessment([0.05], base_risk=10.0)
        expected = round(10.0 + (1.0 - (1.0 - 0.05)) * 90.0, 4)
        self.assertAlmostEqual(risk, expected, places=2)

    def test_large_factors_compound_sublinearly(self) -> None:
        factors = [0.3, 0.4, 0.2]
        risk = compound_risk_assessment(factors, base_risk=10.0)
        survival = (1 - 0.3) * (1 - 0.4) * (1 - 0.2)
        compound = 1.0 - survival
        expected = round(min(10.0 + compound * 90.0, 100.0), 4)
        self.assertAlmostEqual(risk, expected, places=1)

    def test_compound_less_than_sum(self) -> None:
        factors = [0.3, 0.4, 0.2]
        risk = compound_risk_assessment(factors, base_risk=10.0)
        linear_sum = sum(factors)
        linear_risk = round(min(10.0 + linear_sum * 90.0, 100.0), 4)
        self.assertLess(risk, linear_risk)

    def test_two_large_factors(self) -> None:
        factors = [0.5, 0.5]
        risk = compound_risk_assessment(factors, base_risk=10.0)
        expected = round(10.0 + (1.0 - 0.25) * 90.0, 4)
        self.assertAlmostEqual(risk, expected, places=1)

    def test_many_small_factors_approximate_sum(self) -> None:
        factors = [0.01] * 5
        risk = compound_risk_assessment(factors, base_risk=10.0)
        survival = (1 - 0.01) ** 5
        expected = round(10.0 + (1.0 - survival) * 90.0, 4)
        self.assertAlmostEqual(risk, expected, places=0)

    def test_risk_bounded_by_100(self) -> None:
        factors = [0.9, 0.9, 0.9]
        risk = compound_risk_assessment(factors, base_risk=10.0)
        self.assertLessEqual(risk, 100.0)

    def test_independent_factors_multiply(self) -> None:
        single_a = compound_risk_assessment([0.4], base_risk=0.0)
        single_b = compound_risk_assessment([0.3], base_risk=0.0)
        combined = compound_risk_assessment([0.4, 0.3], base_risk=0.0)
        survival = (1.0 - 0.4) * (1.0 - 0.3)
        expected = round((1.0 - survival) * 90.0, 4)
        self.assertAlmostEqual(combined, expected, places=1)
        self.assertLess(combined, single_a + single_b)


if __name__ == "__main__":
    unittest.main()
