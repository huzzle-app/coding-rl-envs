import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load(paths: list[str]) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for path in paths:
        if path.endswith('.py'):
            mod = path[:-3].replace('/', '.')
            suite.addTests(loader.loadTestsFromName(mod))
        else:
            suite.addTests(loader.discover('tests', pattern='*_test.py'))
    return suite


def main() -> int:
    targets = sys.argv[1:] or ["tests"]
    suite = load(targets)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    total = result.testsRun
    failed = len(result.failures)
    errors = len(result.errors)
    passed = total - failed - errors
    print(f"TB_SUMMARY total={total} passed={passed} failed={failed} errors={errors}")
    return 0 if failed == 0 and errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
