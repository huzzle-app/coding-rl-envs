import unittest

from ionveil.queue import should_shed


class QueueTests(unittest.TestCase):
    def test_should_shed_uses_hard_limit(self) -> None:
        self.assertFalse(should_shed(9, 10, False))
        self.assertTrue(should_shed(11, 10, False))
        self.assertTrue(should_shed(8, 10, True))


if __name__ == "__main__":
    unittest.main()
