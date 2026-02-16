#!/usr/bin/env python3
"""Unified test runner that emits a parseable summary line for Harbor and RL wrappers."""

from __future__ import annotations

import argparse
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Anti-reward-hacking: expected test file inventory
# If test files are deleted or renamed, the runner will detect it.
# ---------------------------------------------------------------------------
EXPECTED_TEST_FILES = {
    "tests/unit/models_test.py",
    "tests/unit/orbit_test.py",
    "tests/unit/policy_test.py",
    "tests/unit/queue_test.py",
    "tests/unit/resilience_test.py",
    "tests/unit/routing_test.py",
    "tests/unit/scheduler_test.py",
    "tests/unit/security_test.py",
    "tests/unit/statistics_test.py",
    "tests/unit/telemetry_test.py",
    "tests/unit/workflow_test.py",
    "tests/unit/dependency_test.py",
    "tests/unit/advanced_test.py",
    "tests/unit/extended_test.py",
    "tests/integration/mission_flow_test.py",
    "tests/integration/replay_governance_test.py",
    "tests/integration/security_pipeline_test.py",
    "tests/integration/service_mesh_flow_test.py",
    "tests/chaos/failover_storm_test.py",
    "tests/chaos/routing_partition_test.py",
    "tests/stress/hyper_matrix_test.py",
    "tests/stress/service_mesh_matrix_test.py",
    "tests/services/contracts_test.py",
    "tests/services/gateway_service_test.py",
    "tests/services/identity_service_test.py",
    "tests/services/intake_service_test.py",
    "tests/services/mission_service_test.py",
    "tests/services/orbit_service_test.py",
    "tests/services/planner_service_test.py",
    "tests/services/resilience_service_test.py",
    "tests/services/policy_service_test.py",
    "tests/services/security_service_test.py",
    "tests/services/audit_service_test.py",
    "tests/services/analytics_service_test.py",
    "tests/services/notifications_service_test.py",
    "tests/services/reporting_service_test.py",
}

MIN_EXPECTED_TESTS = 7000

# Anti-reward-hacking: SHA256 prefix checksums of critical test files.
# Detects content tampering (e.g. gutting assertions, replacing tests with pass).
CRITICAL_FILE_CHECKSUMS = {
    "tests/unit/models_test.py": "9c09329630642d41",
    "tests/unit/orbit_test.py": "6297d3399c523a09",
    "tests/unit/policy_test.py": "0dff6e1a817ff169",
    "tests/unit/queue_test.py": "09be0d808b0d9e83",
    "tests/unit/resilience_test.py": "36688df3701cda45",
    "tests/unit/routing_test.py": "b47f77bac4dd4359",
    "tests/unit/scheduler_test.py": "0d57d4caaa84c478",
    "tests/unit/security_test.py": "2781122acfa8d3e0",
    "tests/unit/statistics_test.py": "efc9decf545096dc",
    "tests/unit/telemetry_test.py": "257ad05d99744ae0",
    "tests/unit/workflow_test.py": "4b702a0dd67cafa7",
    "tests/unit/dependency_test.py": "29db37868cd847ae",
    "tests/unit/advanced_test.py": "d2f9fb971892ffcc",
    "tests/unit/extended_test.py": "b6ea560ce7b657a3",
}


def _verify_test_integrity() -> list[str]:
    """Check that expected test files exist, haven't been emptied, and haven't been tampered with."""
    errors = []
    for rel_path in sorted(EXPECTED_TEST_FILES):
        full = ROOT / rel_path
        if not full.exists():
            errors.append(f"missing test file: {rel_path}")
        elif full.stat().st_size < 100:
            errors.append(f"test file suspiciously small (<100 bytes): {rel_path}")

    # Verify checksums of critical files
    for rel_path, expected_prefix in CRITICAL_FILE_CHECKSUMS.items():
        full = ROOT / rel_path
        if full.exists():
            actual = hashlib.sha256(full.read_bytes()).hexdigest()[:16]
            if actual != expected_prefix:
                errors.append(f"checksum mismatch for {rel_path} (content tampered)")
    return errors


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

    # Anti-reward-hacking: verify test file integrity before running
    integrity_errors = _verify_test_integrity()
    if integrity_errors:
        print("TEST INTEGRITY CHECK FAILED:", file=sys.stderr)
        for err in integrity_errors:
            print(f"  - {err}", file=sys.stderr)
        print(f"TB_SUMMARY total=0 passed=0 failed=0 errors=0")
        return 1

    suite = build_suite(args.targets)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures)
    errors = len(result.errors)
    passed = total - failed - errors

    # Anti-reward-hacking: verify minimum test count
    if not args.targets and total < MIN_EXPECTED_TESTS:
        print(
            f"INTEGRITY WARNING: Expected >= {MIN_EXPECTED_TESTS} tests, "
            f"only {total} discovered. Possible test tampering.",
            file=sys.stderr,
        )
        print(f"TB_SUMMARY total=0 passed=0 failed=0 errors=0")
        return 1

    print(f"TB_SUMMARY total={total} passed={passed} failed={failed} errors={errors}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
