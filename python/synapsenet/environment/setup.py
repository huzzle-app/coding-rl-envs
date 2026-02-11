"""
SynapseNet RL Environment Wrapper
Terminal Bench v2 - Distinguished Engineer AI/ML Platform

This environment provides an interface for RL agents to interact with
a buggy microservices AI/ML platform. The agent must identify and fix
120 interconnected bugs across 15 services.

Usage:
    # With Docker (recommended)
    docker compose up -d  # Start all services
    docker compose -f docker-compose.test.yml up --build  # Run tests

    # Environment API
    from environment import SynapseNetEnvironment

    env = SynapseNetEnvironment(max_steps=300)
    obs = env.reset()

    while not done:
        action = agent.act(obs)
        obs, reward, done, info = env.step(action)
"""
import os
import re
import shlex
import subprocess
import shutil
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path

from environment.reward import RewardCalculator, BUG_TEST_MAPPING


@dataclass
class StepResult:
    """Result of an environment step."""
    observation: Dict[str, Any]
    reward: float
    done: bool
    truncated: bool
    info: Dict[str, Any]


class SynapseNetEnvironment:
    """
    RL Environment for the SynapseNet AI/ML platform.

    This environment wraps a buggy microservices codebase with 120 intentional bugs.
    The agent's goal is to fix all bugs and get all 750+ tests passing.

    Attributes:
        max_steps: Maximum number of steps before truncation
        project_root: Root directory of the SynapseNet project
        observation_space: Description of the observation structure
        action_space: Description of valid actions
    """

    # Observation space describes the structure of observations returned by step/reset
    observation_space = {
        "type": "dict",
        "fields": {
            "step": {"type": "int", "min": 0, "max": 300, "description": "Current step number"},
            "max_steps": {"type": "int", "description": "Maximum steps allowed"},
            "test_results": {
                "type": "optional_dict",
                "fields": {
                    "total": {"type": "int", "min": 0, "description": "Total number of tests"},
                    "passed": {"type": "int", "min": 0, "description": "Number of passing tests"},
                    "failed": {"type": "int", "min": 0, "description": "Number of failing tests"},
                    "pass_rate": {"type": "float", "min": 0.0, "max": 1.0, "description": "Ratio of passing tests"},
                    "errors": {"type": "list_str", "description": "Error messages (up to 10)"},
                    "raw_output": {"type": "str", "description": "Raw pytest output (up to 10000 chars)"},
                },
            },
            "action_result": {
                "type": "optional_dict",
                "fields": {
                    "success": {"type": "bool", "description": "Whether the action succeeded"},
                    "type": {"type": "str", "description": "Action type that was executed"},
                    "error": {"type": "optional_str", "description": "Error message if failed"},
                },
            },
            "project_root": {"type": "str", "description": "Absolute path to the project root"},
        },
    }

    # Action space describes valid actions the agent can take
    action_space = {
        "type": "dict",
        "fields": {
            "type": {
                "type": "enum",
                "values": ["edit", "create", "delete", "command"],
                "description": "Type of action to execute",
            },
            "file": {
                "type": "str",
                "description": "Relative file path (required for edit/create/delete)",
                "constraints": ["Must not contain '..'", "Must be relative to project root"],
            },
            "content": {
                "type": "str",
                "max_length": 100000,
                "description": "File content (required for edit, optional for create)",
            },
            "command": {
                "type": "str",
                "max_length": 5000,
                "description": "Shell command to execute (required for command type)",
            },
        },
    }

    # Mapping from source directories to relevant test files for targeted testing
    _FILE_TEST_MAP = {
        "services/gateway/": ["tests/integration/test_service_communication.py"],
        "services/auth/": ["tests/security/test_vulnerabilities.py"],
        "services/models/": [
            "tests/unit/test_ml_pipeline.py",
            "tests/unit/test_model_serving.py",
        ],
        "services/registry/": [
            "tests/unit/test_ml_pipeline.py",
            "tests/unit/test_model_serving.py",
        ],
        "services/training/": [
            "tests/unit/test_ml_pipeline.py",
            "tests/chaos/test_distributed_training.py",
            "tests/integration/test_training_pipeline.py",
        ],
        "services/inference/": [
            "tests/unit/test_model_serving.py",
            "tests/chaos/test_model_serving.py",
            "tests/performance/test_inference_latency.py",
        ],
        "services/features/": [
            "tests/unit/test_feature_store.py",
        ],
        "services/pipeline/": [
            "tests/integration/test_training_pipeline.py",
        ],
        "services/experiments/": [
            "tests/unit/test_experiment_tracking.py",
        ],
        "services/monitoring/": [
            "tests/unit/test_ml_pipeline.py",
        ],
        "services/scheduler/": [
            "tests/integration/test_service_communication.py",
        ],
        "services/workers/": [
            "tests/chaos/test_distributed_training.py",
        ],
        "services/storage/": [
            "tests/unit/test_ml_pipeline.py",
            "tests/security/test_vulnerabilities.py",
        ],
        "services/webhooks/": [
            "tests/security/test_vulnerabilities.py",
        ],
        "services/admin/": [
            "tests/security/test_vulnerabilities.py",
        ],
        "shared/clients/": [
            "tests/integration/test_service_communication.py",
            "tests/chaos/test_distributed_training.py",
        ],
        "shared/events/": [
            "tests/chaos/test_distributed_training.py",
            "tests/integration/test_service_communication.py",
        ],
        "shared/utils/": [
            "tests/unit/test_ml_pipeline.py",
            "tests/unit/test_model_serving.py",
            "tests/security/test_vulnerabilities.py",
        ],
        "shared/ml/": [
            "tests/unit/test_ml_pipeline.py",
            "tests/unit/test_model_serving.py",
            "tests/unit/test_feature_store.py",
            "tests/chaos/test_distributed_training.py",
        ],
    }

    # How often to run the full test suite (every N mutating steps)
    _FULL_TEST_INTERVAL = 5

    def __init__(
        self,
        max_steps: int = 300,
        project_root: Optional[str] = None,
    ):
        self.max_steps = max_steps
        self.project_root = Path(project_root or os.path.dirname(os.path.dirname(__file__)))
        self.reward_calculator = RewardCalculator()

        self._step_count = 0
        self._mutating_step_count = 0
        self._previous_test_results: Optional[Dict[str, Any]] = None
        self._git_initialized = False

    def reset(self) -> Dict[str, Any]:
        """
        Reset the environment to the initial buggy state.

        Returns:
            Initial observation dictionary
        """
        self._step_count = 0
        self._previous_test_results = None

        # Reset using git
        if self._git_initialized:
            subprocess.run(
                ["git", "checkout", "."],
                cwd=self.project_root,
                capture_output=True,
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=self.project_root,
                capture_output=True,
            )
        else:
            # Initialize git if needed
            if not (self.project_root / ".git").exists():
                subprocess.run(["git", "init"], cwd=self.project_root, capture_output=True)
                subprocess.run(["git", "add", "-A"], cwd=self.project_root, capture_output=True)
                subprocess.run(
                    ["git", "commit", "-m", "Initial buggy state"],
                    cwd=self.project_root,
                    capture_output=True,
                )
            self._git_initialized = True

        return self._get_observation()

    def validate_action(self, action: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate an action before execution.

        Checks:
        - Action type is one of: edit, create, delete, command
        - File paths don't contain '..' (path traversal prevention)
        - Content length is within limits (100KB for file content)
        - Command length is within limits (5KB)

        Args:
            action: The action dictionary to validate

        Returns:
            Tuple of (is_valid, error_message). error_message is empty if valid.
        """
        valid_types = {"edit", "create", "delete", "command"}
        action_type = action.get("type")

        if action_type not in valid_types:
            return False, f"Invalid action type '{action_type}'. Must be one of: {valid_types}"

        # Validate file path for file operations
        if action_type in ("edit", "create", "delete"):
            file_path = action.get("file", "")
            if not file_path:
                return False, f"Action type '{action_type}' requires a 'file' field"
            if ".." in file_path:
                return False, f"File path must not contain '..': {file_path}"
            # Reject absolute paths - must be relative to project root
            if os.path.isabs(file_path):
                return False, f"File path must be relative, not absolute: {file_path}"
            # Verify resolved path stays within project root
            resolved = (self.project_root / file_path).resolve()
            if not resolved.is_relative_to(self.project_root.resolve()):
                return False, "File path escapes project directory"

            # Reject edits to test files
            if action_type in ("edit", "create", "delete"):
                basename = os.path.basename(file_path)
                if (file_path.startswith("tests/") or "/tests/" in file_path
                        or basename.startswith("test_") or basename == "conftest.py"):
                    return False, "Modifying test files is not allowed"

        # Validate content length for edit/create
        if action_type in ("edit", "create"):
            content = action.get("content", "")
            if action_type == "edit" and not content:
                return False, "Action type 'edit' requires a 'content' field"
            if len(content) > 100000:
                return False, f"Content length {len(content)} exceeds maximum 100000 characters"

        # Validate command for command type
        if action_type == "command":
            command = action.get("command", "")
            if not command:
                return False, "Action type 'command' requires a 'command' field"
            if len(command) > 5000:
                return False, f"Command length {len(command)} exceeds maximum 5000 characters"

        return True, ""

    def step(self, action: Dict[str, Any]) -> StepResult:
        """
        Execute an action and return the result.

        Validates the action, executes it, then runs tests. For mutating actions
        (edit/create/delete), runs targeted tests first based on the affected file.
        Every _FULL_TEST_INTERVAL mutating steps, runs the full test suite instead.

        Args:
            action: Dictionary with action details:
                - type: 'edit', 'create', 'delete', 'command'
                - file: File path (for edit/create/delete)
                - content: New content (for edit/create)
                - command: Shell command (for command type)

        Returns:
            StepResult with observation, reward, done, truncated, info
        """
        self._step_count += 1

        # Validate action
        is_valid, error_msg = self.validate_action(action)
        if not is_valid:
            return StepResult(
                observation=self._get_observation(),
                reward=0.0,
                done=False,
                truncated=self._step_count >= self.max_steps,
                info={"step": self._step_count, "validation_error": error_msg},
            )

        # Execute action
        action_result = self._execute_action(action)

        # Determine whether this is a mutating action
        action_type = action.get("type", "unknown")
        is_mutating = action_type in ("edit", "create", "delete")

        if is_mutating:
            self._mutating_step_count += 1

        # Run targeted or full tests depending on step interval
        if is_mutating and (self._mutating_step_count % self._FULL_TEST_INTERVAL != 0):
            # Run targeted tests for faster feedback
            test_results = self._run_targeted_tests(action.get("file", ""))
        else:
            # Run full test suite on command actions or every N mutating steps
            test_results = self._run_tests()

        # Calculate reward
        reward = self.reward_calculator.calculate_reward(
            test_results=test_results,
            previous_results=self._previous_test_results,
            step_count=self._step_count,
            max_steps=self.max_steps,
        )

        # Update previous results
        self._previous_test_results = test_results

        # Check if done - only on full suite runs with actual results
        is_full_run = not test_results.get("targeted", False)
        has_results = test_results.get("total", 0) > 0
        done = is_full_run and has_results and test_results.get("pass_rate", 0) >= 1.0
        truncated = self._step_count >= self.max_steps

        observation = self._get_observation(
            test_results=test_results,
            action_result=action_result,
        )

        info = {
            "step": self._step_count,
            "test_results": test_results,
            "action_result": action_result,
            "bugs_fixed": self._estimate_bugs_fixed(test_results),
            "services_passing": self._get_passing_services(test_results),
        }

        return StepResult(
            observation=observation,
            reward=reward,
            done=done,
            truncated=truncated,
            info=info,
        )

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action on the codebase."""
        action_type = action.get("type", "unknown")

        try:
            if action_type in ("edit", "create", "delete"):
                file_path = (self.project_root / action["file"]).resolve()
                if not file_path.is_relative_to(self.project_root.resolve()):
                    return {"success": False, "error": "Path escapes project directory"}

            if action_type == "edit":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(action["content"])
                return {"success": True, "type": "edit", "file": str(action["file"])}

            elif action_type == "create":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(action.get("content", ""))
                return {"success": True, "type": "create", "file": str(action["file"])}

            elif action_type == "delete":
                if file_path.exists():
                    file_path.unlink()
                return {"success": True, "type": "delete", "file": str(action["file"])}

            elif action_type == "command":
                try:
                    args = shlex.split(action["command"])
                except ValueError as e:
                    return {"success": False, "error": f"Invalid command syntax: {e}"}
                if not args:
                    return {"success": False, "error": "Empty command"}
                safe_commands = {"pytest", "python", "pip", "cat", "ls", "grep", "find", "head", "tail"}
                if args[0] not in safe_commands:
                    return {"success": False, "error": f"Command '{args[0]}' not allowed"}
                dangerous_args = {"--delete", "rm", "eval", "exec", "--system"}
                if dangerous_args & set(args[1:]):
                    return {"success": False, "error": "Dangerous argument blocked"}
                result = subprocess.run(
                    args,
                    shell=False,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                return {
                    "success": result.returncode == 0,
                    "type": "command",
                    "stdout": result.stdout[:5000],
                    "stderr": result.stderr[:5000],
                    "returncode": result.returncode,
                }

            else:
                return {"success": False, "error": f"Unknown action type: {action_type}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _parse_test_output(output: str) -> Dict[str, bool]:
        """Parse verbose pytest output to get per-test pass/fail status."""
        test_detail = {}
        # Match: tests/path::Class::test_name PASSED/FAILED or tests/path::test_name PASSED/FAILED
        pattern = r'(tests/\S+::\S+)\s+(PASSED|FAILED|ERROR)'
        for match in re.finditer(pattern, output):
            nodeid, status = match.groups()
            # Extract bare test function name for matching against BUG_TEST_MAPPING
            parts = nodeid.split("::")
            test_name = parts[-1]
            bare_name = re.sub(r'\[.*\]$', '', test_name)
            test_detail[bare_name] = (status == "PASSED")
        return test_detail

    def _run_tests(self) -> Dict[str, Any]:
        """Run the test suite and return results."""
        try:
            result = subprocess.run(
                [
                    "python", "-m", "pytest",
                    "--tb=short",
                    "-v",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Parse results from pytest summary line
            passed_tests = 0
            failed_tests = 0
            error_tests = 0
            errors = []

            output = result.stdout + result.stderr
            for line in output.split("\n"):
                match = re.search(r"(\d+) passed", line)
                if match:
                    passed_tests = int(match.group(1))
                match = re.search(r"(\d+) failed", line)
                if match:
                    failed_tests = int(match.group(1))
                match = re.search(r"(\d+) error", line)
                if match:
                    error_tests = int(match.group(1))
                if "ERROR" in line or "FAILED" in line:
                    errors.append(line)

            total_tests = passed_tests + failed_tests + error_tests

            return {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests + error_tests,
                "pass_rate": passed_tests / total_tests if total_tests > 0 else 0.0,
                "errors": errors[:10],
                "raw_output": output[:10000],
                "test_detail": self._parse_test_output(output),
            }

        except subprocess.TimeoutExpired:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "pass_rate": 0.0,
                "errors": ["Test execution timed out"],
            }
        except Exception as e:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "pass_rate": 0.0,
                "errors": [str(e)],
            }

    def _run_targeted_tests(self, file_path: str) -> Dict[str, Any]:
        """
        Run only tests relevant to the modified file for faster feedback.

        Uses _FILE_TEST_MAP to determine which test files are relevant to the
        changed source file. Falls back to running the full suite if no mapping
        is found.

        Args:
            file_path: Relative path of the file that was modified

        Returns:
            Test results dictionary matching _run_tests() format
        """
        # Find matching test files based on the source directory
        target_tests = set()
        for source_prefix, test_files in self._FILE_TEST_MAP.items():
            if file_path.startswith(source_prefix):
                target_tests.update(test_files)

        # If no specific mapping found, fall back to full suite
        if not target_tests:
            return self._run_tests()

        try:
            cmd = [
                "python", "-m", "pytest",
                "--tb=short",
                "-v",
            ] + sorted(target_tests)

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Parse results (same logic as _run_tests)
            passed_tests = 0
            failed_tests = 0
            error_tests = 0
            errors = []

            output = result.stdout + result.stderr
            for line in output.split("\n"):
                match = re.search(r"(\d+) passed", line)
                if match:
                    passed_tests = int(match.group(1))
                match = re.search(r"(\d+) failed", line)
                if match:
                    failed_tests = int(match.group(1))
                match = re.search(r"(\d+) error", line)
                if match:
                    error_tests = int(match.group(1))
                if "ERROR" in line or "FAILED" in line:
                    errors.append(line)

            total_tests = passed_tests + failed_tests + error_tests

            return {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests + error_tests,
                "pass_rate": passed_tests / total_tests if total_tests > 0 else 0.0,
                "errors": errors[:10],
                "raw_output": output[:10000],
                "test_detail": self._parse_test_output(output),
                "targeted": True,
                "test_files": sorted(target_tests),
            }

        except subprocess.TimeoutExpired:
            return {
                "total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0,
                "errors": ["Targeted test execution timed out"],
                "targeted": True,
            }
        except Exception as e:
            return {
                "total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0,
                "errors": [str(e)],
                "targeted": True,
            }

    def _get_observation(
        self,
        test_results: Optional[Dict[str, Any]] = None,
        action_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get current observation state."""
        return {
            "step": self._step_count,
            "max_steps": self.max_steps,
            "test_results": test_results,
            "action_result": action_result,
            "project_root": str(self.project_root),
        }

    def _estimate_bugs_fixed(self, test_results: Dict[str, Any]) -> int:
        """Count bugs fixed based on per-test results."""
        test_detail = test_results.get("test_detail", {})
        if not test_detail:
            return 0
        fixed = 0
        for bug_id, test_names in BUG_TEST_MAPPING.items():
            matching = [name for name in test_names if name in test_detail]
            if matching and all(test_detail.get(name, False) for name in matching):
                fixed += 1
        return fixed

    def _get_passing_services(self, test_results: Dict[str, Any]) -> List[str]:
        """Get list of services with all tests passing."""
        return []

    def get_bug_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions of all 120 bugs in the environment.

        Returns:
            Dictionary mapping bug IDs to descriptions
        """
        return {
            # Setup Hell (L1-L15)
            'L1': 'Circular imports between shared.ml and shared.clients - ImportError on startup',
            'L2': 'Missing import guard for optional ML dependency in model_loader.py',
            'L3': 'Database migration references non-existent table - MigrationError',
            'L4': 'Kafka auto.create.topics.enable is disabled - TopicNotFound',
            'L5': 'Service startup order dependency - ConnectionRefused on boot',
            'L6': 'Consul not registered properly - ServiceUnavailable',
            'L7': 'Redis cluster mode config wrong - CROSSSLOT error',
            'L8': 'Elasticsearch index mapping missing - IndexNotFoundException',
            'L9': 'MinIO bucket creation fails silently - artifact upload 404',
            'L10': 'Celery broker URL uses wrong protocol - ConnectionError',
            'L11': 'CORS misconfiguration blocks cross-service calls - 403 on preflight',
            'L12': 'Logging config uses wrong handler class - AttributeError on init',
            'L13': 'Schema validation init fails on circular reference - RecursionError',
            'L14': 'Feature store bootstrap needs training service running first',
            'L15': 'Worker registration needs scheduler service active',

            # ML Pipeline (M1-M10)
            'M1': 'Model version mismatch on rollback - wrong weights loaded',
            'M2': 'Gradient accumulation overflow with large batch sizes - NaN loss',
            'M3': 'Batch normalization statistics leak between train/eval mode',
            'M4': 'Feature drift detection false positive on correlated features',
            'M5': 'Training data iterator not shuffled between epochs',
            'M6': 'Learning rate scheduler off-by-one on step count',
            'M7': 'Checkpoint corruption on concurrent save operations',
            'M8': 'Mixed-precision NaN propagation with certain architectures',
            'M9': 'Data augmentation seed not set - non-reproducible results',
            'M10': 'Tokenizer padding mismatch between training and inference',

            # Distributed Training (A1-A10)
            'A1': 'Parameter server race condition - inconsistent weight updates',
            'A2': 'Gradient all-reduce deadlock under asymmetric topology',
            'A3': 'Data parallelism shard overlap - duplicate training samples',
            'A4': 'Model parallelism tensor split error at layer boundaries',
            'A5': 'Elastic scaling worker registration race on join/leave',
            'A6': 'Checkpoint barrier timeout - workers not synchronized',
            'A7': 'Gradient compression lossy threshold too aggressive',
            'A8': 'Ring-allreduce topology mismatch after node failure',
            'A9': 'Async SGD staleness bound not enforced - stale gradients applied',
            'A10': 'Fault-tolerant training resume from wrong checkpoint',

            # Model Serving (B1-B10)
            'B1': 'Model loading memory leak - unreleased GPU/CPU tensors',
            'B2': 'Request batching timeout too short - partial batches dropped',
            'B3': 'A/B testing traffic split precision loss - wrong percentages',
            'B4': 'Canary deployment rollback race - both versions serving',
            'B5': 'Model warm-up missing - first requests get cold-start latency',
            'B6': 'Prediction cache key collision - wrong predictions returned',
            'B7': 'Input validation schema drift - new features not validated',
            'B8': 'Output postprocessing type mismatch - float vs int labels',
            'B9': 'Concurrent model swap race - partial model served',
            'B10': 'Auto-scaling metric lag - scaling decisions based on stale metrics',

            # Feature Store (C1-C8)
            'C1': 'Feature consistency between online/offline stores diverged',
            'C2': 'Point-in-time join timezone bug - features from wrong timestamp',
            'C3': 'Feature drift detection threshold float comparison fails',
            'C4': 'Feature transformation pipeline ordering wrong',
            'C5': 'Feature backfill race condition - incomplete backfill served',
            'C6': 'Feature schema evolution breaks backward compatibility',
            'C7': 'Feature serving cache stampede on popular features',
            'C8': 'Feature dependency graph has undetected cycle',

            # Data Pipeline (D1-D10)
            'D1': 'Data validation schema mismatch between producer and consumer',
            'D2': 'Schema evolution backward compatibility check missing',
            'D3': 'Backfill duplicate processing - same records processed twice',
            'D4': 'Late-arriving data window close too early - data dropped',
            'D5': 'Partition key distribution skew - hot partitions',
            'D6': 'Checkpoint interval too large - data loss on failure',
            'D7': 'Dead letter queue overflow - failed messages dropped',
            'D8': 'Pipeline DAG cycle detection missing - infinite loop',
            'D9': 'Data lineage tracking gap - missing transformation steps',
            'D10': 'Transformation idempotency broken - reprocessing changes results',

            # Experiment Tracking (E1-E8)
            'E1': 'Metric logging race condition - lost metrics under concurrency',
            'E2': 'Hyperparameter comparison float equality - wrong best model',
            'E3': 'Reproducibility seed propagation missing to sub-processes',
            'E4': 'Experiment fork parent reference broken after deletion',
            'E5': 'Artifact upload partial failure - incomplete artifacts stored',
            'E6': 'Comparison query N+1 - performance degrades with experiments',
            'E7': 'Metric aggregation overflow with large experiment counts',
            'E8': 'Tag search SQL injection via experiment filter endpoint',

            # Database & Transactions (F1-F10)
            'F1': 'Cross-database transaction isolation - phantom reads across DBs',
            'F2': 'Connection pool per-service exhaustion - deadlock under load',
            'F3': 'Saga compensation order wrong - partial rollback on failure',
            'F4': 'Outbox pattern message loss - events never published to Kafka',
            'F5': 'Read replica lag ignored - stale reads after write',
            'F6': 'Optimistic locking retry limit - updates silently dropped',
            'F7': 'Foreign key across databases - orphaned references',
            'F8': 'Batch insert partial failure - inconsistent state',
            'F9': 'Index hint forcing wrong plan - query timeout',
            'F10': 'Deadlock from inconsistent lock ordering - transaction abort',

            # Authentication & RBAC (G1-G6)
            'G1': 'JWT propagation loses claims - permission denied downstream',
            'G2': 'Token refresh race across services - intermittent 401',
            'G3': 'Service-to-service auth bypass - unauthorized internal calls',
            'G4': 'RBAC permission cache stale - old permissions used',
            'G5': 'API key rotation window - both old and new rejected',
            'G6': 'mTLS certificate chain validation failure - MITM vulnerability',

            # Caching & Performance (H1-H8)
            'H1': 'Model cache eviction during inference - request fails mid-prediction',
            'H2': 'Feature cache TTL race - expired features served briefly',
            'H3': 'Prediction cache key hash collision - wrong results returned',
            'H4': 'Cache stampede on model deploy - database overwhelmed',
            'H5': 'Distributed cache consistency - nodes disagree on cached model',
            'H6': 'Cache aside pattern stale data - old predictions cached forever',
            'H7': 'TTL randomization missing - synchronized expiry storm',
            'H8': 'LRU eviction priority wrong - frequently-used model evicted',

            # Security (I1-I10)
            'I1': 'SQL injection in experiment filter - data exfiltration',
            'I2': 'SSRF via webhook URL - internal network scan possible',
            'I3': 'Insecure model deserialization via pickle - RCE vulnerability',
            'I4': 'Rate limit bypass via X-Forwarded-For header spoofing',
            'I5': 'IDOR on model endpoints - access to other tenants models',
            'I6': 'XXE in model metadata XML parsing - file disclosure',
            'I7': 'Mass assignment on model update - privilege escalation',
            'I8': 'Timing attack on API key comparison - key enumeration',
            'I9': 'Path traversal in artifact download - file system access',
            'I10': 'ReDoS in search query regex - CPU exhaustion',

            # Observability (J1-J7)
            'J1': 'Trace context lost across Kafka - broken distributed traces',
            'J2': 'Log correlation ID mismatch - cannot track requests across services',
            'J3': 'Metrics cardinality explosion - monitoring system crashes',
            'J4': 'Health check false positive - dead dependency marked healthy',
            'J5': 'Error aggregation groups wrong - alerts fire incorrectly',
            'J6': 'Model inference latency histogram bucket overflow',
            'J7': 'Distributed tracing span leak - memory grows unbounded',

            # Configuration (K1-K8)
            'K1': 'Environment variable precedence wrong - config file overrides env',
            'K2': 'Service discovery stale TTL - connections to dead instances',
            'K3': 'Feature flag evaluation race - inconsistent behavior',
            'K4': 'Config reload not atomic - partial config state used',
            'K5': 'Secret rotation timing - old secrets still accepted',
            'K6': 'YAML anchor merge conflict - missing configuration values',
            'K7': 'Dynamic config version mismatch - services disagree on config',
            'K8': 'Consul KV watch miss - config changes not propagated',
        }

    def get_setup_bugs(self) -> List[str]:
        """Get list of setup bug IDs that must be fixed first."""
        return [f'L{i}' for i in range(1, 16)]

    def gym_step(self, action: Dict[str, Any]):
        """Gymnasium-compatible step returning (obs, reward, done, truncated, info)."""
        result = self.step(action)
        return result.observation, result.reward, result.done, result.truncated, result.info

    def get_service_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about each microservice."""
        return {
            'gateway': {
                'path': 'services/gateway',
                'framework': 'FastAPI',
                'port': 8000,
                'bugs': ['L11', 'I4', 'J1', 'K1'],
            },
            'auth': {
                'path': 'services/auth',
                'framework': 'Django',
                'port': 8001,
                'bugs': ['G1', 'G2', 'G3', 'G4', 'G5', 'I7', 'I8'],
            },
            'models': {
                'path': 'services/models',
                'framework': 'FastAPI',
                'port': 8002,
                'bugs': ['M1', 'I5', 'I7'],
            },
            'registry': {
                'path': 'services/registry',
                'framework': 'Django',
                'port': 8003,
                'bugs': ['M1', 'M6', 'B4'],
            },
            'training': {
                'path': 'services/training',
                'framework': 'Celery/FastAPI',
                'port': 8004,
                'bugs': ['A1', 'A2', 'A3', 'M2', 'M5', 'M8', 'M9'],
            },
            'inference': {
                'path': 'services/inference',
                'framework': 'FastAPI',
                'port': 8005,
                'bugs': ['B1', 'B2', 'B3', 'B5', 'B7', 'B8', 'B9', 'H1'],
            },
            'features': {
                'path': 'services/features',
                'framework': 'Django',
                'port': 8006,
                'bugs': ['C1', 'C2', 'C4', 'C5', 'C6', 'C7', 'C8'],
            },
            'pipeline': {
                'path': 'services/pipeline',
                'framework': 'Celery/FastAPI',
                'port': 8007,
                'bugs': ['D1', 'D3', 'D4', 'D5', 'D8'],
            },
            'experiments': {
                'path': 'services/experiments',
                'framework': 'Django',
                'port': 8008,
                'bugs': ['E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E8'],
            },
            'monitoring': {
                'path': 'services/monitoring',
                'framework': 'FastAPI',
                'port': 8009,
                'bugs': ['M3', 'M4', 'J5', 'J6'],
            },
            'scheduler': {
                'path': 'services/scheduler',
                'framework': 'Django',
                'port': 8010,
                'bugs': ['L15', 'K3'],
            },
            'workers': {
                'path': 'services/workers',
                'framework': 'Celery',
                'port': 8011,
                'bugs': ['A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10'],
            },
            'storage': {
                'path': 'services/storage',
                'framework': 'FastAPI',
                'port': 8012,
                'bugs': ['L9', 'M7', 'I9'],
            },
            'webhooks': {
                'path': 'services/webhooks',
                'framework': 'Django',
                'port': 8013,
                'bugs': ['I2', 'J3'],
            },
            'admin': {
                'path': 'services/admin',
                'framework': 'Django',
                'port': 8014,
                'bugs': ['G6', 'K4'],
            },
        }
