"""
TalentFlow RL Environment

Provides a Gym-like interface for the Django debugging environment.
"""
import os
import shlex
import subprocess
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .reward import RewardCalculator, TestResult, parse_pytest_output


@dataclass
class StepResult:
    """Result of taking an action in the environment."""
    observation: Dict[str, Any]
    reward: float
    done: bool
    truncated: bool
    info: Dict[str, Any]


class TalentFlowEnvironment:
    """
    RL Environment for Django debugging challenge (Terminal Bench v2).

    This environment provides:
    - A buggy Django codebase with 25 interconnected bugs:
      - 12 original bugs (A1-E2): Database, Celery, OAuth, Config, Business logic
      - 13 additional bugs (F1-I2, S5-S10): Heisenbugs, environmental, concurrency, security, setup
    - 250+ pytest tests that verify bug fixes
    - Sparse reward function with thresholds and regression penalties
    - Setup bugs that prevent the project from even running initially

    Infrastructure (Docker):
    - PostgreSQL 15 for database
    - Redis 7 for caching and Celery broker
    - Celery workers for async tasks
    - Celery beat for scheduled tasks

    Quick Start:
        # Start services
        docker-compose up -d db redis

        # Run tests
        docker-compose -f docker-compose.test.yml up --build

        # Or use the RL environment
        env = TalentFlowEnvironment()
        obs = env.reset()

    The agent must first fix setup bugs (S5-S10) before tests can run:
    - Setup bug
    - Setup bug
    - Setup bug
    - Setup bug
    - Setup bug
    - S10: Wrong settings module path in manage.py

    Usage:
        env = TalentFlowEnvironment()
        obs = env.reset()

        while not done:
            action = agent.get_action(obs)  # e.g., file edit
            result = env.step(action)
            obs = result.observation
            reward = result.reward
            done = result.done
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
        'apps/candidates/': ['tests/unit/test_candidates.py', 'tests/unit/test_encoding.py', 'tests/unit/test_scoring.py'],
        'apps/jobs/': ['tests/unit/test_jobs.py', 'tests/unit/test_scoring.py'],
        'apps/interviews/': ['tests/unit/test_interviews.py', 'tests/unit/test_datetime.py'],
        'apps/analytics/': ['tests/unit/test_analytics.py', 'tests/unit/test_caching.py'],
        'apps/accounts/': ['tests/unit/test_accounts.py', 'tests/unit/test_auth_permissions.py', 'tests/security/'],
        'talentflow/': ['tests/unit/test_setup.py', 'tests/integration/test_celery.py'],
        'requirements.txt': ['tests/unit/test_setup.py'],
    }

    def __init__(
        self,
        project_dir: Optional[str] = None,
        max_steps: int = 100,
        timeout: int = 300,
    ):
        """
        Initialize the environment.

        Args:
            project_dir: Path to the Django project. If None, uses current directory.
            max_steps: Maximum number of actions before truncation.
            timeout: Timeout for pytest runs in seconds.
        """
        self.project_dir = Path(project_dir) if project_dir else Path(__file__).parent.parent
        self.max_steps = max_steps
        self.timeout = timeout
        self.reward_calculator = RewardCalculator(max_steps=max_steps)

        self._step_count = 0
        self._previous_results: List[TestResult] = []
        self._done = False
        self._truncated = False
        self._full_run_interval = 3
        self._steps_since_full_run = 0

        # Store initial state for reset
        self._initial_state_backup = None

    def reset(self) -> Dict[str, Any]:
        """
        Reset the environment to initial buggy state.

        Returns:
            Initial observation dictionary
        """
        # Reset to initial buggy state
        self._restore_initial_state()

        self._step_count = 0
        self._previous_results = []
        self._done = False
        self._truncated = False
        self._steps_since_full_run = 0

        # Run initial tests to get baseline
        test_results = self._run_tests()
        initial_reward = self._calculate_reward(test_results)

        return {
            'test_results': self._format_test_results(test_results),
            'reward': initial_reward.total,
            'step_count': self._step_count,
            'files_changed': [],
            'project_structure': self._get_project_structure(),
            'bugs_remaining': self._count_remaining_bugs(test_results),
        }

    def step(self, action: Dict[str, Any]) -> StepResult:
        """
        Execute an action and return the result.

        Args:
            action: Dictionary with action details:
                - 'type': 'edit', 'read', 'run_command'
                - 'file': path to file (for edit/read)
                - 'content': new content (for edit)
                - 'command': command to run (for run_command)

        Returns:
            StepResult with observation, reward, done, truncated, info
        """
        if self._done or self._truncated:
            return self._get_terminal_result()

        self._step_count += 1

        # Execute the action
        action_result = self._execute_action(action)

        # Only run tests when the action modifies state
        action_type = action.get('type', 'unknown')
        if action_type in ('edit', 'run_command'):
            self._steps_since_full_run += 1
            changed_file = action.get('file', '')

            # Run targeted tests first for instant feedback
            targeted_results = self._run_targeted_tests(changed_file) if changed_file else []

            # Full suite runs every _full_run_interval mutating steps
            # OR when all targeted tests pass (whichever comes first)
            all_targeted_pass = targeted_results and all(r.passed for r in targeted_results)
            if self._steps_since_full_run >= self._full_run_interval or all_targeted_pass:
                test_results = self._run_tests()
                self._steps_since_full_run = 0
            elif targeted_results:
                # Merge targeted results into previous full results
                targeted_names = {r.name for r in targeted_results}
                merged = [r for r in self._previous_results if r.name not in targeted_names]
                merged.extend(targeted_results)
                test_results = merged
            else:
                test_results = self._run_tests()
                self._steps_since_full_run = 0
        else:
            test_results = self._previous_results

        # Calculate reward
        reward_breakdown = self._calculate_reward(test_results)

        # Check termination conditions
        all_tests_pass = len(test_results) > 0 and all(r.passed for r in test_results)
        self._done = all_tests_pass
        self._truncated = self._step_count >= self.max_steps

        # Build observation
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
                'completion_bonus': reward_breakdown.completion_bonus,
                'bug_bonus': reward_breakdown.bug_bonus,
                'efficiency_bonus': reward_breakdown.efficiency_bonus,
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
        """
        Validate an action before execution.

        Returns None if valid, or an error dict if invalid.
        """
        action_type = action.get('type', 'unknown')
        if action_type not in ('edit', 'read', 'run_command'):
            return {'success': False, 'error': f'Invalid action type: {action_type}'}

        file_path = action.get('file', '')
        if len(file_path) > 256:
            return {'success': False, 'error': 'File path exceeds 256 characters'}
        if '..' in file_path:
            return {'success': False, 'error': 'Path traversal not allowed'}
        if file_path and os.path.isabs(file_path):
            return {'success': False, 'error': 'Absolute paths not allowed'}
        if file_path:
            resolved = (self.project_dir / file_path).resolve()
            if not resolved.is_relative_to(self.project_dir.resolve()):
                return {'success': False, 'error': 'Path escapes project directory'}

        # Reject edits to test files
        if action_type == 'edit' and file_path:
            basename = os.path.basename(file_path)
            if (file_path.startswith('tests/') or '/tests/' in file_path
                    or basename.startswith('test_') or basename == 'conftest.py'):
                return {'success': False, 'error': 'Editing test files is not allowed'}

        content = action.get('content', '')
        if len(content) > 100_000:
            return {'success': False, 'error': 'Content exceeds 100K character limit'}

        command = action.get('command', '')
        if len(command) > 1000:
            return {'success': False, 'error': 'Command exceeds 1000 character limit'}

        return None

    def _run_targeted_tests(self, changed_file: str) -> List[TestResult]:
        """
        Run only the tests relevant to a changed file for fast feedback.

        Args:
            changed_file: Relative path to the changed file.

        Returns:
            List of TestResult from targeted test run.
        """
        test_paths = []
        for prefix, tests in self._FILE_TEST_MAP.items():
            if changed_file.startswith(prefix) or changed_file == prefix:
                test_paths.extend(tests)

        if not test_paths:
            return []

        # Deduplicate while preserving order
        seen = set()
        unique_paths = []
        for p in test_paths:
            if p not in seen:
                seen.add(p)
                unique_paths.append(p)

        try:
            result = subprocess.run(
                ['pytest', '--tb=no', '-v', '--no-header', '-q'] + unique_paths,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, 'DJANGO_SETTINGS_MODULE': 'talentflow.settings.testing'},
            )
            return parse_pytest_output(result.stdout + result.stderr)
        except (subprocess.TimeoutExpired, Exception):
            return []

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action."""
        validation_error = self.validate_action(action)
        if validation_error is not None:
            return validation_error

        action_type = action.get('type', 'unknown')

        if action_type == 'edit':
            return self._execute_edit(action)
        elif action_type == 'read':
            return self._execute_read(action)
        elif action_type == 'run_command':
            return self._execute_command(action)
        else:
            return {'success': False, 'error': f'Unknown action type: {action_type}'}

    def _execute_edit(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a file edit action."""
        file_path = (self.project_dir / action.get('file', '')).resolve()
        if not file_path.is_relative_to(self.project_dir.resolve()):
            return {'success': False, 'error': 'Path escapes project directory'}
        content = action.get('content', '')

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return {'success': True, 'file': str(file_path)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _execute_read(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a file read action."""
        file_path = (self.project_dir / action.get('file', '')).resolve()
        if not file_path.is_relative_to(self.project_dir.resolve()):
            return {'success': False, 'error': 'Path escapes project directory'}

        try:
            content = file_path.read_text()
            return {'success': True, 'content': content}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _execute_command(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command safely."""
        command = action.get('command', '')

        try:
            args = shlex.split(command)
        except ValueError as e:
            return {'success': False, 'error': f'Invalid command syntax: {e}'}

        if not args:
            return {'success': False, 'error': 'Empty command'}

        # Restrict to safe commands (exact match, not prefix)
        safe_commands = {'pytest', 'python', 'pip', 'cat', 'ls', 'grep'}
        if args[0] not in safe_commands:
            return {'success': False, 'error': 'Command not allowed'}

        # Block dangerous subcommands
        dangerous_args = {'--delete', 'rm', 'eval', 'exec', '--system'}
        if dangerous_args & set(args[1:]):
            return {'success': False, 'error': 'Dangerous argument blocked'}

        try:
            result = subprocess.run(
                args,
                shell=False,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
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
        """Run pytest and return results."""
        try:
            result = subprocess.run(
                ['pytest', '--tb=no', '-v', '--no-header', '-q'],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, 'DJANGO_SETTINGS_MODULE': 'talentflow.settings.testing'},
            )
            return parse_pytest_output(result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            return []
        except Exception:
            return []

    def _calculate_reward(self, results: List[TestResult]):
        """Calculate reward from test results."""
        return self.reward_calculator.calculate(
            results,
            self._step_count,
            self._previous_results,
        )

    def _format_test_results(self, results: List[TestResult]) -> Dict[str, Any]:
        """Format test results for observation."""
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

    def _count_remaining_bugs(self, results: List[TestResult]) -> Dict[str, bool]:
        """Count which bugs are still present."""
        from .reward import BUG_TEST_MAPPING

        bugs = {}
        test_status = {r.name: r.passed for r in results}

        for bug_id, test_names in BUG_TEST_MAPPING.items():
            matching = [name for name in test_names if name in test_status]
            if not matching:
                # No matching tests found → bug is NOT fixed
                bugs[bug_id] = True
            else:
                bug_fixed = all(test_status.get(name, False) for name in matching)
                bugs[bug_id] = not bug_fixed  # True if bug still exists

        return bugs

    def _get_project_structure(self) -> List[str]:
        """Get project directory structure."""
        structure = []
        for path in self.project_dir.rglob('*.py'):
            rel_path = path.relative_to(self.project_dir)
            if '__pycache__' not in str(rel_path):
                structure.append(str(rel_path))
        return sorted(structure)

    def _restore_initial_state(self):
        """Restore the project to initial buggy state using git."""
        subprocess.run(
            ['git', 'checkout', '.'],
            cwd=self.project_dir,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            ['git', 'clean', '-fd'],
            cwd=self.project_dir,
            capture_output=True,
            timeout=30,
        )

    def _get_terminal_result(self) -> StepResult:
        """Get result for terminal state."""
        return StepResult(
            observation={'terminal': True},
            reward=0.0,
            done=self._done,
            truncated=self._truncated,
            info={'message': 'Episode has ended'},
        )

    # Properties for environment inspection

    @property
    def step_count(self) -> int:
        """Current step count."""
        return self._step_count

    @property
    def is_done(self) -> bool:
        """Whether episode is complete (all tests pass)."""
        return self._done

    @property
    def is_truncated(self) -> bool:
        """Whether episode was truncated (max steps reached)."""
        return self._truncated

    def get_bug_descriptions(self) -> Dict[str, str]:
        """Get bug IDs present in the environment."""
        from .reward import BUG_TEST_MAPPING
        return {bug_id: bug_id for bug_id in BUG_TEST_MAPPING}

    def get_success_criteria(self) -> str:
        """Get success criteria for the environment."""
        return "All 250+ pytest tests must pass to complete the challenge."

    def get_setup_bugs(self) -> Dict[str, str]:
        """Get setup-specific bug IDs."""
        from .reward import BUG_CATEGORIES
        return {bug_id: bug_id for bug_id in BUG_CATEGORIES.get('setup', [])}

    def gym_step(self, action: Dict[str, Any]) -> Tuple[Dict, float, bool, bool, Dict]:
        """Gymnasium-compatible step returning (obs, reward, done, truncated, info)."""
        result = self.step(action)
        return result.observation, result.reward, result.done, result.truncated, result.info
