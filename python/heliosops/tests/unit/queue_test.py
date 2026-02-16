import unittest

from heliosops.queue import should_shed


class QueueTests(unittest.TestCase):
    def test_should_shed_uses_hard_limit(self) -> None:
        self.assertFalse(should_shed(9, 10, False))
        self.assertTrue(should_shed(11, 10, False))
        self.assertTrue(should_shed(8, 10, True))

    def test_should_shed_exact_limit_does_not_shed(self) -> None:
        self.assertFalse(should_shed(10, 10, False),
                         "depth == limit should NOT shed (strict greater-than)")

    def test_emergency_80_percent_threshold(self) -> None:
        limit = 50
        thresh = int(limit * 0.8)  # 40
        self.assertTrue(should_shed(thresh, limit, True),
                        f"Emergency: depth={thresh} at 80% of {limit} should shed")
        self.assertFalse(should_shed(thresh - 1, limit, True),
                         f"Emergency: depth={thresh - 1} below 80% should not shed")


if __name__ == "__main__":
    unittest.main()
