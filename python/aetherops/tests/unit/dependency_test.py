import unittest

from aetherops.dependency import blocked_nodes, critical_path_nodes, longest_chain, topological_sort


class DependencyTest(unittest.TestCase):
    def test_topological_sort(self) -> None:
        order = topological_sort(["a", "b", "c"], [("a", "b"), ("b", "c")])
        self.assertEqual(order, ["a", "b", "c"])

    def test_cycle_detected(self) -> None:
        with self.assertRaises(ValueError):
            topological_sort(["a", "b"], [("a", "b"), ("b", "a")])

    def test_blocked_nodes(self) -> None:
        blocked = blocked_nodes(["a", "b", "c"], [("a", "b"), ("b", "c")], {"a"})
        self.assertEqual(blocked, {"c"})

    def test_longest_chain(self) -> None:
        depth = longest_chain(["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("a", "d")])
        self.assertEqual(depth, 3)


class DependencyBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in dependency.py."""

    def test_critical_path_includes_full_chain(self) -> None:
        nodes = ["a", "b", "c", "d"]
        edges = [("a", "b"), ("b", "c"), ("a", "d")]
        result = critical_path_nodes(nodes, edges)
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("c", result)
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
