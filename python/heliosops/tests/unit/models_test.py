import unittest

from heliosops.models import DispatchOrder


class ModelTests(unittest.TestCase):
    def test_dispatch_order_urgency(self) -> None:
        order = DispatchOrder("M1", 3, 30)
        self.assertEqual(order.urgency_score(), 120)

    def test_dispatch_order_has_id_field(self) -> None:
        order = DispatchOrder("order-42", 5, 60)
        self.assertTrue(hasattr(order, "id"), "DispatchOrder must have an 'id' attribute")
        self.assertEqual(order.id, "order-42")

    def test_dispatch_order_urgency_formula(self) -> None:
        # urgency = severity * 10 + max(0, 120 - sla_minutes)
        order = DispatchOrder("test", 4, 50)
        expected = 4.0 * 10.0 + max(0.0, 120.0 - 50)
        self.assertAlmostEqual(order.urgency_score(), expected, places=2)


if __name__ == "__main__":
    unittest.main()
