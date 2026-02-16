"""
CacheForge RL Environment

Provides a Gym-like interface for the C++ cache server debugging environment.
Uses cmake/ctest for building and testing.
"""
import os
import shlex
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .reward import RewardCalculator, TestResult, parse_ctest_output


@dataclass
class StepResult:
    """Result of taking an action in the environment."""
    observation: Dict[str, Any]
    reward: float
    done: bool
    truncated: bool
    info: Dict[str, Any]


class CacheForgeEnvironment:
    """
    RL Environment for C++ cache server debugging challenge (Terminal Bench v2).

    This environment provides:
    - A buggy C++20 codebase with 25 interconnected bugs:
      - L1-L4: Setup/Config (static init fiasco, signal UB, stoi, include guards)
      - A1-A5: Concurrency (data race, deadlock, memory ordering, condvar, volatile)
      - B1-B4: Memory (buffer overflow, string_view dangle, vector realloc, double-free)
      - C1-C4: Smart Ptrs (shared_ptr cycle, LRU invalidation, unique_ptr, exception-unsafe)
      - D1-D4: Move/UB (use-after-move, strict aliasing, signed overflow, const move)
      - E1-E4: Security (TTL overflow, format string, buffer overread, key length)
    - 125+ Google Test tests that verify bug fixes
    - Sparse reward function with thresholds and regression penalties
    - Setup bugs that prevent the project from building initially

    Infrastructure (Docker):
    - PostgreSQL 15 for persistence
    - Redis 7 for replication

    Quick Start:
        docker compose up -d
        docker compose -f docker-compose.test.yml up --build

    Usage:
        env = CacheForgeEnvironment()
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
            'reward': {'type': 'Box', 'low': 0.0, 'high': 1.0, 'shape': (1,)},
            'step_count': {'type': 'Discrete', 'n': 101},
            'action_result': {'type': 'Dict'},
            'bugs_remaining': {'type': 'MultiBinary', 'n': 25},
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
        'src/config/': ['unit_tests'],
        'src/server/': ['integration_tests', 'concurrency_tests'],
        'src/protocol/': ['unit_tests', 'security_tests'],
        'src/storage/hashtable': ['unit_tests', 'concurrency_tests'],
        'src/storage/eviction': ['unit_tests'],
        'src/storage/expiry': ['unit_tests', 'concurrency_tests'],
        'src/data/': ['unit_tests'],
        'src/replication/': ['integration_tests'],
        'src/persistence/': ['unit_tests', 'integration_tests'],
        'src/utils/': ['unit_tests'],
        'CMakeLists.txt': ['unit_tests'],
    }

    def __init__(
        self,
        project_dir: Optional[str] = None,
        max_steps: int = 100,
        timeout: int = 300,
    ):
        self.project_dir = Path(project_dir) if project_dir else Path(__file__).parent.parent
        self.build_dir = self.project_dir / 'build'
        self.max_steps = max_steps
        self.timeout = timeout
        self.reward_calculator = RewardCalculator(max_steps=max_steps)

        self._step_count = 0
        self._previous_results: List[TestResult] = []
        self._done = False
        self._truncated = False
        self._full_run_interval = 3
        self._steps_since_full_run = 0

    def reset(self) -> Dict[str, Any]:
        self._restore_initial_state()
        self._step_count = 0
        self._previous_results = []
        self._done = False
        self._truncated = False
        self._steps_since_full_run = 0

        # Try to build first
        build_result = self._build_project()
        test_results = self._run_tests() if build_result else []
        initial_reward = self._calculate_reward(test_results)

        return {
            'test_results': self._format_test_results(test_results),
            'reward': initial_reward.total,
            'step_count': self._step_count,
            'files_changed': [],
            'project_structure': self._get_project_structure(),
            'bugs_remaining': self._count_remaining_bugs(test_results),
            'build_success': build_result,
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

            # Rebuild on source changes
            if changed_file.endswith(('.cpp', '.h', '.txt')):
                self._build_project()

            targeted_results = self._run_targeted_tests(changed_file) if changed_file else []

            all_targeted_pass = targeted_results and all(r.passed for r in targeted_results)
            if self._steps_since_full_run >= self._full_run_interval or all_targeted_pass:
                test_results = self._run_tests()
                self._steps_since_full_run = 0
            elif targeted_results:
                targeted_names = {r.name for r in targeted_results}
                merged = [r for r in self._previous_results if r.name not in targeted_names]
                merged.extend(targeted_results)
                test_results = merged
            else:
                test_results = self._run_tests()
                self._steps_since_full_run = 0
        else:
            test_results = self._previous_results

        reward_breakdown = self._calculate_reward(test_results)
        is_full_run = self._steps_since_full_run == 0  # 0 means we just did a full run
        all_tests_pass = test_results and all(r.passed for r in test_results)
        self._done = is_full_run and all_tests_pass and len(test_results) > 0
        self._truncated = self._step_count >= self.max_steps

        observation = {
            'test_results': self._format_test_results(test_results),
            'reward': reward_breakdown.total,
            'step_count': self._step_count,
            'action_result': action_result,
            'bugs_remaining': self._count_remaining_bugs(test_results),
        }

        info = {
            'reward_breakdown': {
                'test_pass_score': reward_breakdown.test_pass_score,
                'total': reward_breakdown.total,
            },
            'details': reward_breakdown.details,
        }

        self._previous_results = test_results

        return StepResult(
            observation=observation,
            reward=reward_breakdown.total,
            done=self._done,
            truncated=self._truncated,
            info=info,
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
        # Reject edits to environment/reward files
        if action_type == 'edit' and (file_path.startswith('environment/')
                or os.path.basename(file_path) in ('reward.py', 'scoring.py', 'setup.py')):
            return {'success': False, 'error': 'Editing environment files is not allowed'}
        # Prevent removing test targets from CMakeLists.txt
        if action_type == 'edit' and os.path.basename(file_path) == 'CMakeLists.txt':
            content = action.get('content', '')
            required_targets = ['unit_tests', 'integration_tests', 'concurrency_tests', 'security_tests']
            for target in required_targets:
                if target not in content:
                    return {'success': False, 'error': f'CMakeLists.txt must retain test target: {target}'}
        content = action.get('content', '')
        if len(content) > 100_000:
            return {'success': False, 'error': 'Content exceeds 100K character limit'}
        command = action.get('command', '')
        if len(command) > 1000:
            return {'success': False, 'error': 'Command exceeds 1000 character limit'}
        return None

    def _build_project(self) -> bool:
        """Build the project using cmake."""
        try:
            self.build_dir.mkdir(exist_ok=True)
            result = subprocess.run(
                ['cmake', '-B', str(self.build_dir), '-DCMAKE_BUILD_TYPE=Debug'],
                cwd=self.project_dir,
                capture_output=True, text=True, timeout=self.timeout,
            )
            if result.returncode != 0:
                return False
            result = subprocess.run(
                ['cmake', '--build', str(self.build_dir), '--parallel'],
                cwd=self.project_dir,
                capture_output=True, text=True, timeout=self.timeout,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_targeted_tests(self, changed_file: str) -> List[TestResult]:
        test_targets = []
        for prefix, targets in self._FILE_TEST_MAP.items():
            if changed_file.startswith(prefix) or changed_file == prefix:
                test_targets.extend(targets)

        if not test_targets:
            return []

        seen = set()
        unique = [t for t in test_targets if t not in seen and not seen.add(t)]

        try:
            args = ['ctest', '--output-on-failure', '-j', '4']
            args.extend(['-R', '|'.join(unique)])
            result = subprocess.run(
                args, cwd=self.build_dir,
                capture_output=True, text=True, timeout=self.timeout,
            )
            return parse_ctest_output(result.stdout + result.stderr)
        except Exception:
            return []

    def _execute_action(self, action):
        validation_error = self.validate_action(action)
        if validation_error:
            return validation_error
        action_type = action.get('type', 'unknown')
        if action_type == 'edit':
            return self._execute_edit(action)
        elif action_type == 'read':
            return self._execute_read(action)
        elif action_type == 'run_command':
            return self._execute_command(action)
        return {'success': False, 'error': f'Unknown action type: {action_type}'}

    def _execute_edit(self, action):
        file_path = (self.project_dir / action.get('file', '')).resolve()
        if not str(file_path).startswith(str(self.project_dir.resolve())):
            return {'success': False, 'error': 'Path escapes project directory'}
        content = action.get('content', '')
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return {'success': True, 'file': str(file_path)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _execute_read(self, action):
        file_path = (self.project_dir / action.get('file', '')).resolve()
        if not str(file_path).startswith(str(self.project_dir.resolve())):
            return {'success': False, 'error': 'Path escapes project directory'}
        try:
            return {'success': True, 'content': file_path.read_text()}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _execute_command(self, action):
        command = action.get('command', '')
        try:
            args = shlex.split(command)
        except ValueError as e:
            return {'success': False, 'error': f'Invalid command syntax: {e}'}
        if not args:
            return {'success': False, 'error': 'Empty command'}
        safe_commands = {'cmake', 'ctest', 'make', 'cat', 'ls', 'grep', 'find'}
        if args[0] not in safe_commands:
            return {'success': False, 'error': 'Command not allowed'}
        try:
            result = subprocess.run(
                args, shell=False, cwd=self.project_dir,
                capture_output=True, text=True, timeout=self.timeout,
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Command timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _run_tests(self) -> List[TestResult]:
        try:
            result = subprocess.run(
                ['ctest', '--output-on-failure', '-j', '4'],
                cwd=self.build_dir,
                capture_output=True, text=True, timeout=self.timeout,
            )
            return parse_ctest_output(result.stdout + result.stderr)
        except Exception:
            return []

    def _calculate_reward(self, results):
        return self.reward_calculator.calculate(
            results, self._step_count, self._previous_results,
        )

    def _format_test_results(self, results):
        passed = [r.name for r in results if r.passed]
        failed = [r.name for r in results if not r.passed]
        return {
            'total': len(results),
            'passed': len(passed),
            'failed': len(failed),
            'pass_rate': len(passed) / len(results) if results else 0,
            'passed_tests': passed,
            'failed_tests': failed,
        }

    def _count_remaining_bugs(self, results):
        from .reward import BUG_TEST_MAPPING
        bugs = {}
        test_status = {r.name: r.passed for r in results}
        for bug_id, test_names in BUG_TEST_MAPPING.items():
            matching = [n for n in test_names if n in test_status]
            if not matching:
                bugs[bug_id] = True
            else:
                bugs[bug_id] = not all(test_status.get(n, False) for n in matching)
        return bugs

    def _get_project_structure(self):
        structure = []
        for ext in ('*.cpp', '*.h', '*.txt', '*.json'):
            for path in self.project_dir.rglob(ext):
                rel = path.relative_to(self.project_dir)
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
        result = self.step(action)
        return result.observation, result.reward, result.done, result.truncated, result.info
