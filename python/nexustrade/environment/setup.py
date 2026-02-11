"""
NexusTrade RL Environment Wrapper
Terminal Bench v2 - 10x Harder Distributed Trading Platform

This environment provides an interface for RL agents to interact with
a buggy microservices trading platform. The agent must identify and fix
75+ interconnected bugs across 10 services.

Usage:
    # With Docker (recommended)
    docker compose up -d  # Start all services
    docker compose -f docker-compose.test.yml up --build  # Run tests

    # Environment API
    from environment import NexusTradeEnvironment

    env = NexusTradeEnvironment(max_steps=200)
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


class NexusTradeEnvironment:
    """
    RL Environment for the NexusTrade distributed trading platform.

    This environment wraps a buggy microservices codebase with 75+ intentional bugs.
    The agent's goal is to fix all bugs and get all 500+ tests passing.

    Attributes:
        max_steps: Maximum number of steps before truncation
        project_root: Root directory of the NexusTrade project
        observation_space: Description of the observation structure
        action_space: Description of valid actions
    """

    # Observation space describes the structure of observations returned by step/reset
    observation_space = {
        "type": "dict",
        "fields": {
            "step": {"type": "int", "min": 0, "max": 200, "description": "Current step number"},
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
        "services/users/": ["tests/security/test_vulnerabilities.py"],
        "services/orders/": [
            "tests/unit/test_trading_logic.py",
            "tests/unit/test_risk_management.py",
            "tests/security/test_vulnerabilities.py",
        ],
        "services/matching/": [
            "tests/unit/test_trading_logic.py",
            "tests/chaos/test_distributed_consensus.py",
        ],
        "services/risk/": ["tests/unit/test_risk_management.py"],
        "services/settlement/": ["tests/unit/test_trading_logic.py"],
        "services/market-data/": [
            "tests/integration/test_service_communication.py",
            "tests/chaos/test_distributed_consensus.py",
        ],
        "services/notifications/": ["tests/integration/test_service_communication.py"],
        "services/audit/": ["tests/integration/test_service_communication.py"],
        "shared/clients/": [
            "tests/integration/test_service_communication.py",
            "tests/chaos/test_distributed_consensus.py",
        ],
        "shared/events/": [
            "tests/chaos/test_distributed_consensus.py",
            "tests/integration/test_service_communication.py",
        ],
        "shared/utils/": [
            "tests/unit/test_trading_logic.py",
            "tests/unit/test_risk_management.py",
            "tests/security/test_vulnerabilities.py",
        ],
    }

    # How often to run the full test suite (every N mutating steps)
    _FULL_TEST_INTERVAL = 5

    def __init__(
        self,
        max_steps: int = 200,
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
            if action_type == "edit":
                basename = os.path.basename(file_path)
                if (file_path.startswith("tests/") or "/tests/" in file_path
                        or basename.startswith("test_") or basename == "conftest.py"):
                    return False, "Editing test files is not allowed"

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

        # Check if done — only on full suite runs with actual results
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
        # Would need more detailed test results to implement properly
        return []

    def get_bug_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions of all 75+ bugs in the environment.

        Returns:
            Dictionary mapping bug IDs to descriptions
        """
        return {
            # Distributed Consensus (A1-A8)
            'A1': 'Split-brain on network partition - duplicate order execution',
            'A2': 'Leader election race - inconsistent state during failover',
            'A3': 'Distributed lock timeout too short - lock stolen during long operations',
            'A4': 'Consensus quorum off-by-one - writes succeed with minority',
            'A5': 'Version vector comparison bug - lost updates on merge',
            'A6': 'Gossip protocol message ordering - stale data propagation',
            'A7': 'CAP violation in cache - reads return stale during partition',
            'A8': 'Two-phase commit coordinator crash - stuck transactions',

            # Event Sourcing (B1-B8)
            'B1': 'Event ordering across partitions - out-of-order processing',
            'B2': 'Idempotency key collision - duplicate side effects',
            'B3': 'Event replay skips checkpoints - corrupted aggregate state',
            'B4': 'Projection race condition - inconsistent read models',
            'B5': 'Event schema evolution bug - deserialization failures',
            'B6': 'Tombstone compaction race - deleted entities resurrect',
            'B7': 'Snapshot corruption on concurrent write - invalid restore point',
            'B8': 'Event timestamp clock skew - wrong ordering on merge',

            # Service Communication (C1-C7)
            'C1': 'Circuit breaker never opens - cascade failure',
            'C2': 'Retry storm on partial failure - resource exhaustion',
            'C3': 'Request coalescing data leak - cross-user data exposure',
            'C4': 'gRPC deadline propagation - upstream timeout ignored',
            'C5': 'Service mesh routing stale - requests to dead instances',
            'C6': 'Message serialization version mismatch - silent data corruption',
            'C7': 'Bulkhead thread pool exhaustion - unrelated services affected',

            # Database & Transactions (D1-D10)
            'D1': 'Cross-database transaction isolation - phantom reads',
            'D2': 'Connection pool per-service exhaustion - deadlock',
            'D3': 'Saga compensation order wrong - partial rollback',
            'D4': 'Outbox pattern message loss - events never published',
            'D5': 'Read replica lag ignore - stale reads after write',
            'D6': 'Optimistic locking retry limit - updates silently dropped',
            'D7': 'Foreign key across databases - orphaned references',
            'D8': 'Batch insert partial failure - inconsistent state',
            'D9': 'Index hint forcing wrong plan - query timeout',
            'D10': 'Deadlock from inconsistent lock ordering - transaction abort',

            # Authentication Chain (E1-E6)
            'E1': 'JWT propagation loses claims - permission denied downstream',
            'E2': 'Token refresh race across services - intermittent 401',
            'E3': 'Service-to-service auth bypass - unauthorized internal calls',
            'E4': 'Permission cache invalidation race - stale permissions',
            'E5': 'API key rotation window - both old and new rejected',
            'E6': 'mTLS certificate chain validation - MITM vulnerability',

            # Trading Logic (F1-F8)
            'F1': 'Price matching floating point - penny differences',
            'F2': 'Order queue priority inversion - wrong execution order',
            'F3': 'Partial fill rounding - position mismatch',
            'F4': 'Stop-loss trigger race - execution at wrong price',
            'F5': 'Market close edge case - orders after close accepted',
            'F6': 'Cross-margin calculation - wrong liquidation threshold',
            'F7': 'Fee calculation precision loss - account balance drift',
            'F8': 'Position netting timezone bug - wrong daily P&L',

            # Risk Management (G1-G6)
            'G1': 'Exposure limit check race - over-exposure allowed',
            'G2': 'Real-time P&L cache stale - wrong risk decisions',
            'G3': 'Margin call threshold comparison - off-by-one liquidation',
            'G4': 'Credit check service timeout - order rejected unfairly',
            'G5': 'Multi-leg order risk atomic check - partial approval',
            'G6': 'Historical VaR calculation overflow - NaN propagation',

            # Caching & Performance (H1-H6)
            'H1': 'Cache stampede on expiry - database overwhelmed',
            'H2': 'Hot key concentration - single Redis node overload',
            'H3': 'Cache aside pattern race - stale data cached forever',
            'H4': 'TTL randomization missing - synchronized expiry',
            'H5': 'Bloom filter false positive threshold - cache misses increase',
            'H6': 'LRU eviction priority wrong - important data evicted',

            # Security Vulnerabilities (I1-I8)
            'I1': 'SQL injection in order filter - data exfiltration',
            'I2': 'SSRF via webhook URL - internal network scan',
            'I3': 'Insecure deserialization - RCE via pickle',
            'I4': 'Rate limit bypass via header - DoS possible',
            'I5': 'IDOR on account endpoints - cross-account access',
            'I6': 'XML external entity (XXE) - file disclosure',
            'I7': 'Mass assignment on user update - privilege escalation',
            'I8': 'Timing attack on auth - password enumeration',

            # Observability (J1-J5)
            'J1': 'Trace context lost across Kafka - broken distributed traces',
            'J2': 'Log correlation ID mismatch - can\'t track requests',
            'J3': 'Metrics cardinality explosion - monitoring crashes',
            'J4': 'Health check false positive - dead service marked healthy',
            'J5': 'Error aggregation groups wrong - alerts fire incorrectly',

            # Configuration Hell (K1-K8)
            'K1': 'Environment variable precedence - wrong values used',
            'K2': 'Service discovery stale TTL - connection to wrong instance',
            'K3': 'Feature flag evaluation race - inconsistent behavior',
            'K4': 'Config reload not atomic - partial config state',
            'K5': 'Secret rotation timing - old secrets still work',
            'K6': 'YAML anchor merge conflict - missing configuration',
            'K7': 'Dynamic config version mismatch - services disagree',
            'K8': 'Consul KV watch miss - config changes ignored',

            # Setup Hell (L1-L10)
            'L1': 'Circular imports across services - ImportError on startup',
            'L2': 'Missing protobuf compilation - ModuleNotFoundError',
            'L3': 'Database migration ordering - MigrationError',
            'L4': 'Kafka topic auto-create disabled - TopicNotFound',
            'L5': 'Service startup order dependency - ConnectionRefused',
            'L6': 'Consul not registered - ServiceUnavailable',
            'L7': 'Redis cluster mode config - CROSSSLOT error',
            'L8': 'SSL certificate missing - TLS handshake failure',
            'L9': 'Incompatible package versions - AttributeError',
            'L10': 'Docker network isolation - DNS resolution failure',
        }

    def get_setup_bugs(self) -> List[str]:
        """Get list of setup bug IDs that must be fixed first."""
        return ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'L8', 'L9', 'L10']

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
                'bugs': ['C5', 'I2', 'I4', 'J1'],
            },
            'auth': {
                'path': 'services/auth',
                'framework': 'Django',
                'port': 8001,
                'bugs': ['E1', 'E2', 'E3', 'E4', 'E5', 'I7', 'I8'],
            },
            'users': {
                'path': 'services/users',
                'framework': 'Django',
                'port': 8002,
                'bugs': ['I5', 'I7'],
            },
            'orders': {
                'path': 'services/orders',
                'framework': 'Django',
                'port': 8003,
                'bugs': ['A3', 'B2', 'D4', 'D6', 'F3', 'F7', 'G1', 'I1'],
            },
            'matching': {
                'path': 'services/matching',
                'framework': 'Python',
                'port': 8004,
                'bugs': ['A1', 'A3', 'B1', 'B8', 'F1', 'F2', 'F4', 'F5', 'H2', 'H3'],
            },
            'risk': {
                'path': 'services/risk',
                'framework': 'Django',
                'port': 8005,
                'bugs': ['G1', 'G2', 'G3', 'G4', 'G5', 'G6'],
            },
            'settlement': {
                'path': 'services/settlement',
                'framework': 'Django',
                'port': 8006,
                'bugs': ['D3', 'F8'],
            },
            'market-data': {
                'path': 'services/market-data',
                'framework': 'FastAPI',
                'port': 8007,
                'bugs': ['H1', 'H2', 'H3', 'H4'],
            },
            'notifications': {
                'path': 'services/notifications',
                'framework': 'Celery',
                'port': 8008,
                'bugs': ['C7', 'J3'],
            },
            'audit': {
                'path': 'services/audit',
                'framework': 'Django',
                'port': 8009,
                'bugs': ['J1', 'J2'],
            },
        }
