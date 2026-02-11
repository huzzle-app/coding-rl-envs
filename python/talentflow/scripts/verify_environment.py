#!/usr/bin/env python3
"""
TalentFlow Environment Verification Script
Terminal Bench v2

Run this script to verify the RL environment is set up correctly.

Usage:
    python scripts/verify_environment.py [--with-docker]

Without --with-docker: Checks Python code, imports, test discovery
With --with-docker: Also runs Docker tests (requires Docker)
"""

import sys
import os
import subprocess
import argparse

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_result(check, passed, details=""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {check}")
    if details:
        print(f"         {details}")


def check_python_version():
    """Check Python version is 3.9+"""
    version = sys.version_info
    passed = version.major == 3 and version.minor >= 9
    print_result(
        "Python version",
        passed,
        f"Found {version.major}.{version.minor}.{version.micro}"
    )
    return passed


def check_project_structure():
    """Check required directories exist"""
    required_dirs = [
        'apps/accounts',
        'apps/candidates',
        'apps/jobs',
        'apps/interviews',
        'apps/analytics',
        'apps/common',
        'environment',
        'tests/unit',
        'tests/integration',
        'tests/system',
        'tests/security',
    ]

    all_exist = True
    for dir_path in required_dirs:
        exists = os.path.isdir(dir_path)
        if not exists:
            print_result(f"Directory: {dir_path}", False)
            all_exist = False

    if all_exist:
        print_result("Project structure", True, f"{len(required_dirs)} directories found")

    return all_exist


def check_setup_bugs_exist():
    """Verify setup bugs are present (environment should be buggy initially)"""
    bugs_found = []

    
    try:
        with open('apps/candidates/utils.py', 'r') as f:
            content = f.read()
            if 'from apps.jobs.utils import' in content:
                bugs_found.append('setup bug')
    except FileNotFoundError:
        pass

    
    if not os.path.exists('apps/common/helpers/__init__.py'):
        bugs_found.append('setup bug')

    
    try:
        with open('apps/candidates/migrations/0005_candidatenote_candidatedocument.py', 'r') as f:
            content = f.read()
            if "'candidates', '0003" in content:
                bugs_found.append('setup bug')
    except FileNotFoundError:
        pass

    
    try:
        with open('.env.example', 'r') as f:
            content = f.read()
            if 'DEBUG="false"' in content:
                bugs_found.append('setup bug')
    except FileNotFoundError:
        pass

    
    try:
        with open('requirements.txt', 'r') as f:
            content = f.read()
            if 'psycopg2-binary' in content and 'psycopg2>=' in content:
                bugs_found.append('setup bug')
    except FileNotFoundError:
        pass

    
    try:
        with open('manage.py', 'r') as f:
            content = f.read()
            if "settings.development" in content and "talentflow.settings" not in content:
                bugs_found.append('S10: Wrong settings module path')
    except FileNotFoundError:
        pass

    print_result(
        "Setup bugs present",
        len(bugs_found) >= 4,
        f"Found {len(bugs_found)} setup bugs"
    )
    for bug in bugs_found:
        print(f"         - {bug}")

    return len(bugs_found) >= 4


def check_environment_module():
    """Check RL environment module loads"""
    try:
        from environment.reward import RewardCalculator, BUG_TEST_MAPPING

        num_bugs = len(BUG_TEST_MAPPING)
        print_result(
            "Reward module",
            num_bugs >= 20,
            f"Found {num_bugs} bug mappings"
        )
        return num_bugs >= 20
    except Exception as e:
        print_result("Reward module", False, str(e))
        return False


def check_environment_api():
    """Check RL environment API"""
    try:
        from environment.setup import TalentFlowEnvironment

        env = TalentFlowEnvironment(max_steps=10)

        # Check methods exist
        has_reset = callable(getattr(env, 'reset', None))
        has_step = callable(getattr(env, 'step', None))
        has_bugs = callable(getattr(env, 'get_bug_descriptions', None))

        if has_bugs:
            bugs = env.get_bug_descriptions()
            num_bugs = len(bugs)
        else:
            num_bugs = 0

        passed = has_reset and has_step and has_bugs and num_bugs >= 20
        print_result(
            "Environment API",
            passed,
            f"reset={has_reset}, step={has_step}, bugs={num_bugs}"
        )
        return passed
    except Exception as e:
        print_result("Environment API", False, str(e))
        return False


def discover_tests():
    """Discover pytest tests without running them"""
    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', '--collect-only', '-q', 'tests/'],
            capture_output=True,
            text=True,
            timeout=60
        )

        # Count test items
        lines = result.stdout.strip().split('\n')
        test_count = 0
        for line in lines:
            if '::test_' in line or line.strip().startswith('test_'):
                test_count += 1

        # Also check the summary line
        for line in lines:
            if 'test' in line and 'selected' in line:
                import re
                match = re.search(r'(\d+)\s+test', line)
                if match:
                    test_count = int(match.group(1))
                    break

        passed = test_count >= 200
        print_result(
            "Test discovery",
            passed,
            f"Found {test_count} tests"
        )
        return passed, test_count
    except subprocess.TimeoutExpired:
        print_result("Test discovery", False, "Timeout")
        return False, 0
    except Exception as e:
        print_result("Test discovery", False, str(e))
        return False, 0


def check_docker_files():
    """Check Docker configuration files exist"""
    files = [
        'Dockerfile',
        'docker-compose.yml',
        'docker-compose.test.yml',
    ]

    all_exist = all(os.path.exists(f) for f in files)
    print_result(
        "Docker files",
        all_exist,
        f"Found {sum(1 for f in files if os.path.exists(f))}/{len(files)} files"
    )
    return all_exist


def run_docker_tests():
    """Run tests in Docker (requires Docker)"""
    print("\n  Running Docker tests (this may take a few minutes)...")

    try:
        result = subprocess.run(
            ['docker', 'compose', '-f', 'docker-compose.test.yml', 'up',
             '--build', '--abort-on-container-exit'],
            capture_output=True,
            text=True,
            timeout=300
        )

        # Check output for test results
        output = result.stdout + result.stderr

        # Look for pytest summary
        passed = 'passed' in output.lower() or 'failed' in output.lower()
        print_result(
            "Docker test run",
            passed,
            "Tests executed in Docker"
        )

        # Show summary
        for line in output.split('\n'):
            if 'passed' in line.lower() or 'failed' in line.lower() or 'error' in line.lower():
                print(f"         {line.strip()}")

        return passed
    except subprocess.TimeoutExpired:
        print_result("Docker test run", False, "Timeout (5 min)")
        return False
    except FileNotFoundError:
        print_result("Docker test run", False, "Docker not installed")
        return False
    except Exception as e:
        print_result("Docker test run", False, str(e))
        return False


def main():
    parser = argparse.ArgumentParser(description='Verify TalentFlow RL Environment')
    parser.add_argument('--with-docker', action='store_true',
                        help='Also run Docker-based tests')
    args = parser.parse_args()

    # Change to project directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)

    print("\n" + "="*60)
    print("  TalentFlow RL Environment Verification")
    print("  Terminal Bench v2")
    print("="*60)

    results = {}

    # Basic checks
    print_header("Basic Checks")
    results['python'] = check_python_version()
    results['structure'] = check_project_structure()
    results['docker_files'] = check_docker_files()

    
    print_header("Bug Verification (should find bugs)")
    results['setup_bugs'] = check_setup_bugs_exist()

    # Module checks
    print_header("Module Checks")
    results['reward'] = check_environment_module()
    results['env_api'] = check_environment_api()

    # Test discovery
    print_header("Test Discovery")
    results['tests'], test_count = discover_tests()

    # Docker tests (optional)
    if args.with_docker:
        print_header("Docker Tests")
        results['docker'] = run_docker_tests()

    # Summary
    print_header("Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  Checks passed: {passed}/{total}")

    if passed == total:
        print("\n  ✓ Environment is ready for RL training!")
        print("  Note: Initial tests SHOULD fail (that's the challenge)")
    else:
        print("\n  ✗ Some checks failed. Review the output above.")

    print("\n  Next steps:")
    print("  1. Run on server: docker compose -f docker-compose.test.yml up --build")
    print("  2. Observe test failures (expected with bugs)")
    print("  3. Use RL agent to fix bugs and improve test pass rate")
    print()

    return 0 if passed >= total - 1 else 1


if __name__ == '__main__':
    sys.exit(main())
