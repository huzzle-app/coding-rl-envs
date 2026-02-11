import unittest

from heliosops.models import DispatchOrder


class ModelTests(unittest.TestCase):
    def test_dispatch_order_urgency(self) -> None:
        order = DispatchOrder("M1", 3, 30)
        self.assertEqual(order.urgency_score(), 120)


if __name__ == "__main__":
    unittest.main()
