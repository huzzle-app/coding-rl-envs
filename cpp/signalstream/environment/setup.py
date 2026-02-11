"""
SignalStream RL Environment

Provides a Gym-like interface for the C++ streaming platform debugging environment.
Uses cmake/ctest for building and testing.
"""
import os
import shlex
import subprocess
import shutil
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .reward import RewardCalculator, BUG_TEST_MAPPING, BUG_CATEGORIES, BUG_DEPENDENCIES


@dataclass
class StepResult:
    """Result of taking an action in the environment."""
    observation: Dict[str, Any]
    reward: float
    done: bool
    truncated: bool
    info: Dict[str, Any]


class SignalStreamEnvironment:
    """
    RL Environment for C++ streaming platform debugging (Terminal Bench v2).

    This environment provides:
    - A buggy C++20 microservices platform with 75 interconnected bugs across
      10 services + shared library:
      - L1-L5: Setup/Config (static init, CMake, health check)
      - A1-A10: Concurrency (ABA, memory ordering, false sharing, races, condvar, rwlock, spinlock)
      - B1-B6: Memory (alignment, pool lifetime, string_view UAF, iterator, delete, padding)
      - C1-C5: Smart Ptrs (shared_ptr cycle, unique_ptr, shared_from_this, weak_ptr, dtor)
      - D1-D5: UB (signed overflow, strict aliasing, uninit, sequence point, dangling ternary)
      - E1-E6: Event/Distributed (ordering, idempotency, subscription, snapshot, compression, DLQ)
      - F1-F7: Numerical (float, overflow, off-by-one, NaN, accumulate, division, precision)
      - G1-G6: Database (pool leak, SQL injection, stmt leak, iterator, N+1, conn string)
      - H1-H5: Distributed State (check-then-act, lock expiry, circuit breaker, retry, split-brain)
      - I1-I7: Security (buffer overflow, path traversal, rate limit, JWT, timing, RNG, CORS)
      - J1-J5: Observability (trace context, cardinality, registration, log level, log injection)
      - K1-K8: Templates (SFINAE, ADL, constexpr, forwarding, variant, CTAD, concepts, requires)
    - 510+ Google Test tests that verify bug fixes
    - Very sparse reward function (8 thresholds) with regression penalties

    Infrastructure (Docker):
    - Kafka + Zookeeper for event streaming
    - PostgreSQL 15 for persistence
    - Redis 7 for caching
    - InfluxDB 2 for time-series
    - etcd 3.5 for service discovery

    Services: Gateway, Auth, Ingest, Router, Transform, Aggregate,
              Storage, Query, Alert, Monitor

    Usage:
        env = SignalStreamEnvironment()
        obs = env.reset()
        while not done:
            action = agent.get_action(obs)
            result = env.step(action)
    """

    observation_space = {
        'type': 'Dict',
        'spaces': {
            'test_results': {
                'type': 'Dict',
                'keys': ['total', 'passed', 'failed', 'pass_rate', 'passed_tests', 'failed_tests'],
            },
            'reward': {'type': 'Box', 'low': -1.0, 'high': 1.0, 'shape': (1,)},
            'step_count': {'type': 'Discrete', 'n': 201},
            'action_result': {'type': 'Dict'},
            'bugs_remaining': {'type': 'MultiBinary', 'n': 75},
            'services_status': {'type': 'Dict'},
        },
    }

    action_space = {
        'type': 'Dict',
        'spaces': {
            'type': {'type': 'Discrete', 'values': ['edit', 'read', 'run_command']},
            'file': {'type': 'Text', 'max_length': 256},
            'content': {'type': 'Text', 'max_length': 100_000},
            'command': {'type': 'Text', 'max_length': 1000},
        },
    }

    _FILE_TEST_MAP = {
        'shared/src/config/': ['ss_unit_tests'],
        'shared/src/networking/': ['ss_unit_tests', 'ss_integration_tests'],
        'shared/src/serialization/': ['ss_unit_tests'],
        'shared/src/concurrency/': ['ss_unit_tests', 'ss_concurrency_tests'],
        'shared/src/memory/': ['ss_unit_tests'],
        'shared/src/templates/': ['ss_unit_tests'],
        'shared/src/observability/': ['ss_unit_tests', 'ss_integration_tests'],
        'services/gateway/': ['ss_unit_tests', 'ss_security_tests', 'ss_integration_tests'],
        'services/auth/': ['ss_unit_tests', 'ss_security_tests'],
        'services/ingest/': ['ss_unit_tests', 'ss_concurrency_tests'],
        'services/router/': ['ss_unit_tests', 'ss_integration_tests'],
        'services/transform/': ['ss_unit_tests'],
        'services/aggregate/': ['ss_unit_tests', 'ss_performance_tests'],
        'services/storage/': ['ss_unit_tests', 'ss_integration_tests', 'ss_chaos_tests'],
        'services/query/': ['ss_unit_tests', 'ss_integration_tests'],
        'services/alert/': ['ss_unit_tests', 'ss_chaos_tests'],
        'services/monitor/': ['ss_unit_tests', 'ss_system_tests'],
        'CMakeLists.txt': ['ss_unit_tests'],
    }

    def __init__(
        self,
        project_dir: Optional[str] = None,
        max_steps: int = 200,
        timeout: int = 600,
    ):
        self.project_dir = Path(project_dir) if project_dir else Path(__file__).parent.parent
        self.build_dir = self.project_dir / 'build'
        self.max_steps = max_steps
        self.timeout = timeout
        self.reward_calculator = RewardCalculator()

        self._step_count = 0
        self._previous_results: Optional[Dict[str, Any]] = None
        self._done = False
        self._truncated = False
        self._full_run_interval = 5
        self._steps_since_full_run = 0

    def reset(self) -> Dict[str, Any]:
        self._restore_initial_state()
        self._step_count = 0
        self._previous_results = None
        self._done = False
        self._truncated = False
        self._steps_since_full_run = 0

        build_ok = self._build_project()
        test_results = self._run_tests() if build_ok else self._empty_results()
        initial_reward = self.reward_calculator.calculate_reward(test_results)

        return {
            'test_results': test_results,
            'reward': initial_reward,
            'step_count': self._step_count,
            'files_changed': [],
            'project_structure': self._get_project_structure(),
            'bugs_remaining': self._count_remaining_bugs(test_results),
            'build_success': build_ok,
        }

    def step(self, action: Dict[str, Any]) -> StepResult:
        if self._done or self._truncated:
            return self._get_terminal_result()

        self._step_count += 1
        action_result = self._execute_action(action)

        action_type = action.get('type', 'unknown')
        if action_type in ('edit', 'run_command'):
            self._steps_since_full_run += 1
            changed_file = action.get('file', '')

            if changed_file.endswith(('.cpp', '.h', '.txt')):
                self._build_project()

            targeted = self._run_targeted_tests(changed_file) if changed_file else None

            if self._steps_since_full_run >= self._full_run_interval:
                test_results = self._run_tests()
                self._steps_since_full_run = 0
            elif targeted:
                test_results = targeted
            else:
                test_results = self._run_tests()
                self._steps_since_full_run = 0
        else:
            test_results = self._previous_results or self._empty_results()

        reward = self.reward_calculator.calculate_reward(
            test_results, self._previous_results, self._step_count, self.max_steps
        )

        pass_rate = test_results.get('pass_rate', 0.0)
        total = test_results.get('total', 0)
        is_full_run = self._steps_since_full_run == 0  # 0 means we just did a full run
        self._done = is_full_run and total > 0 and pass_rate >= 1.0
        self._truncated = self._step_count >= self.max_steps

        observation = {
            'test_results': test_results,
            'reward': reward,
            'step_count': self._step_count,
            'action_result': action_result,
            'bugs_remaining': self._count_remaining_bugs(test_results),
        }

        bug_status = self.reward_calculator.get_bug_status(test_results)
        info = {
            'bugs_fixed': sum(1 for v in bug_status.values() if v),
            'total_bugs': len(BUG_TEST_MAPPING),
            'dependency_stats': self.reward_calculator.get_dependency_stats(),
        }

        self._previous_results = test_results

        return StepResult(
            observation=observation, reward=reward,
            done=self._done, truncated=self._truncated, info=info,
        )

    def validate_action(self, action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        action_type = action.get('type', 'unknown')
        if action_type not in ('edit', 'read', 'run_command'):
            return {'success': False, 'error': f'Invalid action type: {action_type}'}
        file_path = action.get('file', '')
        if len(file_path) > 256:
            return {'success': False, 'error': 'File path exceeds 256 characters'}
        if '..' in file_path or file_path.startswith('/'):
            return {'success': False, 'error': 'Path traversal not allowed'}
        resolved = (self.project_dir / file_path).resolve()
        if not str(resolved).startswith(str(self.project_dir.resolve())):
            return {'success': False, 'error': 'Path escapes project directory'}
        # Reject edits to test files
        if action_type == 'edit' and (file_path.startswith('tests/') or '/tests/' in file_path
                or os.path.basename(file_path).startswith('test_')):
            return {'success': False, 'error': 'Editing test files is not allowed'}
        content = action.get('content', '')
        if len(content) > 100_000:
            return {'success': False, 'error': 'Content exceeds 100K character limit'}
        command = action.get('command', '')
        if len(command) > 1000:
            return {'success': False, 'error': 'Command exceeds 1000 character limit'}
        return None

    def _build_project(self) -> bool:
        try:
            self.build_dir.mkdir(exist_ok=True)
            r = subprocess.run(
                ['cmake', '-B', str(self.build_dir), '-DCMAKE_BUILD_TYPE=Debug'],
                cwd=self.project_dir, capture_output=True, text=True, timeout=self.timeout,
            )
            if r.returncode != 0:
                return False
            r = subprocess.run(
                ['cmake', '--build', str(self.build_dir), '--parallel'],
                cwd=self.project_dir, capture_output=True, text=True, timeout=self.timeout,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _run_targeted_tests(self, changed_file: str) -> Optional[Dict[str, Any]]:
        targets = []
        for prefix, test_targets in self._FILE_TEST_MAP.items():
            if changed_file.startswith(prefix) or changed_file == prefix:
                targets.extend(test_targets)
        if not targets:
            return None

        seen = set()
        unique = [t for t in targets if t not in seen and not seen.add(t)]

        try:
            args = ['ctest', '--output-on-failure', '-j', '4']
            args.extend(['-R', '|'.join(unique)])
            r = subprocess.run(
                args, cwd=self.build_dir, capture_output=True, text=True, timeout=self.timeout,
            )
            return self._parse_ctest_output(r.stdout + r.stderr)
        except Exception:
            return None

    def _execute_action(self, action):
        err = self.validate_action(action)
        if err:
            return err
        t = action.get('type', 'unknown')
        if t == 'edit':
            return self._execute_edit(action)
        elif t == 'read':
            return self._execute_read(action)
        elif t == 'run_command':
            return self._execute_command(action)
        return {'success': False, 'error': f'Unknown action type: {t}'}

    def _execute_edit(self, action):
        fp = (self.project_dir / action.get('file', '')).resolve()
        if not str(fp).startswith(str(self.project_dir.resolve())):
            return {'success': False, 'error': 'Path escapes project directory'}
        try:
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(action.get('content', ''))
            return {'success': True, 'file': str(fp)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _execute_read(self, action):
        fp = (self.project_dir / action.get('file', '')).resolve()
        if not str(fp).startswith(str(self.project_dir.resolve())):
            return {'success': False, 'error': 'Path escapes project directory'}
        try:
            return {'success': True, 'content': fp.read_text()}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _execute_command(self, action):
        cmd = action.get('command', '')
        try:
            args = shlex.split(cmd)
        except ValueError as e:
            return {'success': False, 'error': f'Invalid syntax: {e}'}
        if not args:
            return {'success': False, 'error': 'Empty command'}
        safe = {'cmake', 'ctest', 'make', 'cat', 'ls', 'grep', 'find'}
        if args[0] not in safe:
            return {'success': False, 'error': 'Command not allowed'}
        try:
            r = subprocess.run(
                args, shell=False, cwd=self.project_dir,
                capture_output=True, text=True, timeout=self.timeout,
            )
            return {'success': r.returncode == 0, 'stdout': r.stdout,
                    'stderr': r.stderr, 'return_code': r.returncode}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Command timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _run_tests(self) -> Dict[str, Any]:
        try:
            r = subprocess.run(
                ['ctest', '--output-on-failure', '-j', '4'],
                cwd=self.build_dir, capture_output=True, text=True, timeout=self.timeout,
            )
            return self._parse_ctest_output(r.stdout + r.stderr)
        except Exception:
            return self._empty_results()

    def _parse_ctest_output(self, output: str) -> Dict[str, Any]:
        passed_tests = []
        failed_tests = []

        ok_pattern = r'\[\s+OK\s+\]\s+\w+\.(test_\w+)'
        fail_pattern = r'\[\s+FAILED\s+\]\s+\w+\.(test_\w+)'

        for m in re.finditer(ok_pattern, output):
            passed_tests.append(m.group(1))
        for m in re.finditer(fail_pattern, output):
            failed_tests.append(m.group(1))

        total = len(passed_tests) + len(failed_tests)
        return {
            'total': total,
            'passed': len(passed_tests),
            'failed': len(failed_tests),
            'pass_rate': len(passed_tests) / total if total > 0 else 0.0,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'passed_test_names': passed_tests,
        }

    def _empty_results(self):
        return {
            'total': 0, 'passed': 0, 'failed': 0, 'pass_rate': 0.0,
            'passed_tests': [], 'failed_tests': [], 'passed_test_names': [],
        }

    def _count_remaining_bugs(self, test_results):
        passed = set(test_results.get('passed_test_names', []))
        bugs = {}
        for bug_id, tests in BUG_TEST_MAPPING.items():
            bugs[bug_id] = not all(t in passed for t in tests)
        return bugs

    def _get_project_structure(self):
        structure = []
        for ext in ('*.cpp', '*.h', '*.txt', '*.json'):
            for p in self.project_dir.rglob(ext):
                rel = p.relative_to(self.project_dir)
                if 'build' not in str(rel) and 'vcpkg' not in str(rel):
                    structure.append(str(rel))
        return sorted(structure)

    def _restore_initial_state(self):
        subprocess.run(['git', 'checkout', '.'], cwd=self.project_dir, capture_output=True, timeout=30)
        subprocess.run(['git', 'clean', '-fd'], cwd=self.project_dir, capture_output=True, timeout=30)
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir, ignore_errors=True)

    def _get_terminal_result(self):
        return StepResult(
            observation={'terminal': True}, reward=0.0,
            done=self._done, truncated=self._truncated,
            info={'message': 'Episode has ended'},
        )

    @property
    def step_count(self):
        return self._step_count

    @property
    def is_done(self):
        return self._done

    @property
    def is_truncated(self):
        return self._truncated

    def gym_step(self, action):
        r = self.step(action)
        return r.observation, r.reward, r.done, r.truncated, r.info
