import unittest

from aetherops.dependency import blocked_nodes, longest_chain, topological_sort


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


if __name__ == "__main__":
    unittest.main()
