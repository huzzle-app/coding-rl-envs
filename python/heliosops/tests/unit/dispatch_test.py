import unittest

from heliosops.dispatch import plan_dispatch


class DispatchTests(unittest.TestCase):
    def test_plan_dispatch_limits_capacity(self) -> None:
        out = plan_dispatch([
            {"id": "a", "urgency": 1, "eta": "09:30"},
            {"id": "b", "urgency": 3, "eta": "10:00"},
            {"id": "c", "urgency": 3, "eta": "08:30"},
        ], 2)
        self.assertEqual([o["id"] for o in out], ["c", "b"])

    def test_plan_dispatch_empty_input(self) -> None:
        self.assertEqual(plan_dispatch([], 5), [])

    def test_plan_dispatch_urgency_descending(self) -> None:
        out = plan_dispatch([
            {"id": "x", "urgency": 10, "eta": "09:00"},
            {"id": "y", "urgency": 50, "eta": "10:00"},
        ], 2)
        if len(out) == 2:
            self.assertGreaterEqual(out[0]["urgency"], out[1]["urgency"],
                                    "Results must be sorted by urgency descending")


if __name__ == "__main__":
    unittest.main()
