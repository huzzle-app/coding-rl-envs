import unittest

from latticeforge.dependency import parallel_execution_groups


class ParallelExecutionGroupsTest(unittest.TestCase):
    def test_linear_chain(self) -> None:
        groups = parallel_execution_groups(
            ["A", "B", "C"], [("A", "B"), ("B", "C")]
        )
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0], {"A"})
        self.assertEqual(groups[1], {"B"})
        self.assertEqual(groups[2], {"C"})

    def test_simple_fan_out(self) -> None:
        groups = parallel_execution_groups(
            ["A", "B", "C"], [("A", "B"), ("A", "C")]
        )
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0], {"A"})
        self.assertEqual(groups[1], {"B", "C"})

    def test_symmetric_diamond(self) -> None:
        groups = parallel_execution_groups(
            ["A", "B", "C", "D"],
            [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")],
        )
        self.assertEqual(len(groups), 3)
        self.assertIn("B", groups[1])
        self.assertIn("C", groups[1])
        self.assertIn("D", groups[2])

    def test_staircase_with_shortcut(self) -> None:
        groups = parallel_execution_groups(
            ["A", "B", "C", "D"],
            [("A", "B"), ("A", "C"), ("B", "C"), ("C", "D")],
        )
        self.assertEqual(len(groups), 4)
        for group in groups:
            if "B" in group:
                self.assertNotIn("C", group)

    def test_mixed_depth_join(self) -> None:
        groups = parallel_execution_groups(
            ["A", "B", "C", "D", "E"],
            [("A", "B"), ("B", "C"), ("A", "D"), ("C", "E"), ("D", "E")],
        )
        for group in groups:
            if "C" in group:
                self.assertNotIn("D", group)
        depth_E = next(i for i, g in enumerate(groups) if "E" in g)
        depth_C = next(i for i, g in enumerate(groups) if "C" in g)
        depth_D = next(i for i, g in enumerate(groups) if "D" in g)
        self.assertGreater(depth_E, depth_C)
        self.assertGreater(depth_E, depth_D)

    def test_cascade_with_branches(self) -> None:
        nodes = ["root", "b1", "b2", "b3", "join"]
        edges = [
            ("root", "b1"), ("root", "b2"), ("root", "b3"),
            ("b1", "b2"), ("b2", "b3"), ("b3", "join"),
        ]
        groups = parallel_execution_groups(nodes, edges)
        self.assertEqual(len(groups), 5)

    def test_dependency_ordering_respected(self) -> None:
        nodes = ["A", "B", "C", "D", "E", "F"]
        edges = [
            ("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"),
            ("B", "E"), ("D", "F"), ("E", "F"),
        ]
        groups = parallel_execution_groups(nodes, edges)
        edge_set = set(edges)
        for group in groups:
            group_list = list(group)
            for i in range(len(group_list)):
                for j in range(i + 1, len(group_list)):
                    self.assertNotIn(
                        (group_list[i], group_list[j]), edge_set
                    )
                    self.assertNotIn(
                        (group_list[j], group_list[i]), edge_set
                    )


if __name__ == "__main__":
    unittest.main()
