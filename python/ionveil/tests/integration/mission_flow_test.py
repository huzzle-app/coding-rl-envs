import unittest

from ionveil.dispatch import plan_dispatch
from ionveil.routing import choose_route
from ionveil.workflow import can_transition


class MissionFlowTests(unittest.TestCase):
    def test_dispatch_routing_workflow_flow(self) -> None:
        orders = plan_dispatch([{"id": "m", "urgency": 4, "eta": "10:00"}], 1)
        route = choose_route([{"channel": "north", "latency": 5}], set())
        self.assertEqual(len(orders), 1)
        self.assertEqual(route["channel"], "north")
        self.assertTrue(can_transition("queued", "allocated"))


if __name__ == "__main__":
    unittest.main()
