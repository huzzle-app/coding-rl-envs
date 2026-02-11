#!/usr/bin/env python3
"""
SynapseNet Environment Verification Script
Terminal Bench v2 - Distinguished Engineer AI/ML Platform

Run this script to verify the RL environment is set up correctly.

Usage:
    python scripts/verify_environment.py [--with-docker]
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
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}]: {check}")
    if details:
        print(f"         {details}")


def check_python_version():
    """Check Python version is 3.11+"""
    version = sys.version_info
    passed = version.major == 3 and version.minor >= 11
    print_result(
        "Python version",
        passed,
        f"Found {version.major}.{version.minor}.{version.micro}"
    )
    return passed


def check_project_structure():
    """Check required directories exist"""
    required_dirs = [
        'services/gateway',
        'services/auth',
        'services/models',
        'services/registry',
        'services/training',
        'services/inference',
        'services/features',
        'services/pipeline',
        'services/experiments',
        'services/monitoring',
        'services/scheduler',
        'services/workers',
        'services/storage',
        'services/webhooks',
        'services/admin',
        'shared/events',
        'shared/clients',
        'shared/utils',
        'shared/ml',
        'environment',
        'tests/unit',
        'tests/integration',
        'tests/security',
        'tests/chaos',
        'tests/performance',
        'tests/contract',
        'tests/system',
    ]

    all_exist = True
    missing = []
    for dir_path in required_dirs:
        exists = os.path.isdir(dir_path)
        if not exists:
            missing.append(dir_path)
            all_exist = False

    if all_exist:
        print_result("Project structure", True, f"{len(required_dirs)} directories found")
    else:
        print_result("Project structure", False, f"Missing: {', '.join(missing[:5])}")

    return all_exist


def check_setup_bugs_exist():
    """Verify setup bugs are present (environment should be buggy initially)"""
    bugs_found = []

    # L1: Circular import
    try:
        with open('shared/__init__.py', 'r') as f:
            content = f.read()
            if 'from shared.clients import' in content or 'from shared.ml import' in content:
                bugs_found.append('L1: Circular import in shared/__init__.py')
    except FileNotFoundError:
        pass

    # L4: Kafka auto-create disabled
    try:
        with open('docker-compose.yml', 'r') as f:
            content = f.read()
            if 'KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"' in content:
                bugs_found.append('L4: Kafka auto-create topics disabled')
    except FileNotFoundError:
        pass

    # L10: Celery broker URL wrong
    try:
        with open('docker-compose.yml', 'r') as f:
            content = f.read()
            if 'CELERY_BROKER_URL=amqp://redis' in content:
                bugs_found.append('L10: Celery broker uses amqp:// for Redis')
    except FileNotFoundError:
        pass

    # L9: MinIO bucket issues
    try:
        with open('shared/ml/model_loader.py', 'r') as f:
            content = f.read()
            if 'bucket_exists' not in content or 'make_bucket' not in content:
                bugs_found.append('L9: MinIO bucket creation not checked')
    except FileNotFoundError:
        pass

    print_result(
        "Setup bugs present",
        len(bugs_found) >= 2,
        f"Found {len(bugs_found)} setup bugs"
    )
    for bug in bugs_found:
        print(f"         - {bug}")

    return len(bugs_found) >= 2


def check_services_count():
    """Check all 15 services exist"""
    services = [
        'gateway', 'auth', 'models', 'registry', 'training',
        'inference', 'features', 'pipeline', 'experiments', 'monitoring',
        'scheduler', 'workers', 'storage', 'webhooks', 'admin',
    ]

    found = []
    for service in services:
        if os.path.isdir(f'services/{service}'):
            found.append(service)

    passed = len(found) == 15
    print_result(
        "Microservices",
        passed,
        f"Found {len(found)}/15 services"
    )
    return passed


def check_environment_module():
    """Check RL environment module loads"""
    try:
        from environment.reward import RewardCalculator, BUG_TEST_MAPPING

        num_bugs = len(BUG_TEST_MAPPING)
        print_result(
            "Reward module",
            num_bugs >= 110,
            f"Found {num_bugs} bug mappings"
        )
        return num_bugs >= 110
    except Exception as e:
        print_result("Reward module", False, str(e))
        return False


def check_environment_api():
    """Check RL environment API"""
    try:
        from environment.setup import SynapseNetEnvironment

        env = SynapseNetEnvironment(max_steps=10)

        # Check methods exist
        has_reset = callable(getattr(env, 'reset', None))
        has_step = callable(getattr(env, 'step', None))
        has_bugs = callable(getattr(env, 'get_bug_descriptions', None))

        if has_bugs:
            bugs = env.get_bug_descriptions()
            num_bugs = len(bugs)
        else:
            num_bugs = 0

        passed = has_reset and has_step and has_bugs and num_bugs >= 110
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

        passed = test_count >= 600  # Should have at least 600 tests for a 750+ test environment
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
        'docker-compose.yml',
        'docker-compose.test.yml',
        'Dockerfile.test',
    ]

    found = [f for f in files if os.path.exists(f)]
    all_exist = len(found) == len(files)
    print_result(
        "Docker files",
        all_exist,
        f"Found {len(found)}/{len(files)} files"
    )
    return all_exist


def main():
    parser = argparse.ArgumentParser(description='Verify SynapseNet RL Environment')
    parser.add_argument('--with-docker', action='store_true',
                        help='Also run Docker-based tests')
    args = parser.parse_args()

    # Change to project directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)

    print("\n" + "="*60)
    print("  SynapseNet RL Environment Verification")
    print("  Terminal Bench v2 - Distinguished Engineer Edition")
    print("="*60)

    results = {}

    # Basic checks
    print_header("Basic Checks")
    results['python'] = check_python_version()
    results['structure'] = check_project_structure()
    results['services'] = check_services_count()
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

    # Docker checks (only when --with-docker is passed)
    if args.with_docker:
        print_header("Docker Checks")
        try:
            docker_result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True, text=True, timeout=15
            )
            containers_up = docker_result.returncode == 0 and docker_result.stdout.strip()
            print_result("Docker services running", bool(containers_up),
                         "Use 'docker compose up -d' to start")
            results['docker'] = bool(containers_up)
        except Exception as e:
            print_result("Docker services running", False, str(e))
            results['docker'] = False

    # Summary
    print_header("Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  Checks passed: {passed}/{total}")

    if passed == total:
        print("\n  Environment is ready for RL training!")
        print("  Note: Initial tests SHOULD fail (that's the challenge)")
    else:
        print("\n  Some checks failed. Review the output above.")

    print("\n  Next steps:")
    print("  1. Run: docker compose up -d")
    print("  2. Run: docker compose -f docker-compose.test.yml up --build")
    print("  3. Observe test failures (expected with bugs)")
    print("  4. Use RL agent to fix bugs and improve test pass rate")
    print()

    return 0 if passed >= total - 1 else 1


if __name__ == '__main__':
    sys.exit(main())
