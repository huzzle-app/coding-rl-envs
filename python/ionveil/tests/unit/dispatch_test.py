import unittest

from ionveil.dispatch import plan_dispatch


class DispatchTests(unittest.TestCase):
    def test_plan_dispatch_limits_capacity(self) -> None:
        out = plan_dispatch([
            {"id": "a", "urgency": 1, "eta": "09:30"},
            {"id": "b", "urgency": 3, "eta": "10:00"},
            {"id": "c", "urgency": 3, "eta": "08:30"},
        ], 2)
        self.assertEqual([o["id"] for o in out], ["c", "b"])


if __name__ == "__main__":
    unittest.main()
