import unittest

from ionveil.workflow import can_transition


class WorkflowTests(unittest.TestCase):
    def test_transition_graph_enforced(self) -> None:
        self.assertTrue(can_transition("queued", "allocated"))
        self.assertFalse(can_transition("queued", "arrived"))


if __name__ == "__main__":
    unittest.main()
