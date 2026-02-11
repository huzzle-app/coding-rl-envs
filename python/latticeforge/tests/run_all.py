#!/usr/bin/env python3
"""Unified test runner that emits a parseable summary line for Harbor and RL wrappers."""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def path_to_module(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized.strip("/").replace("/", ".")


def build_suite(paths: list[str]) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if not paths:
        suite.addTests(loader.discover("tests", pattern="*test.py", top_level_dir=str(ROOT)))
        return suite

    for raw in paths:
        target = Path(raw)
        if target.is_dir():
            suite.addTests(loader.discover(str(target), pattern="*test.py", top_level_dir=str(ROOT)))
        else:
            suite.addTests(loader.loadTestsFromName(path_to_module(raw)))
    return suite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("targets", nargs="*")
    args = parser.parse_args()

    suite = build_suite(args.targets)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures)
    errors = len(result.errors)
    passed = total - failed - errors

    print(f"TB_SUMMARY total={total} passed={passed} failed={failed} errors={errors}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
