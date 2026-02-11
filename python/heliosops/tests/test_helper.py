import unittest


def run_suite(suite: unittest.TestSuite) -> tuple[int, int, int]:
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    total = result.testsRun
    failed = len(result.failures)
    errors = len(result.errors)
    passed = total - failed - errors
    return total, passed, failed + errors
