import unittest

from heliosops.workflow import can_transition


class WorkflowTests(unittest.TestCase):
    def test_transition_graph_enforced(self) -> None:
        self.assertTrue(can_transition("queued", "allocated"))
        self.assertFalse(can_transition("queued", "arrived"))

    def test_on_hold_cannot_jump_to_resolved(self) -> None:
        self.assertFalse(can_transition("on_hold", "resolved"),
                         "on_hold -> resolved should be invalid")

    def test_valid_incident_lifecycle_start(self) -> None:
        self.assertTrue(can_transition("new", "acknowledged"),
                        "new -> acknowledged should be valid")


if __name__ == "__main__":
    unittest.main()
