"""
OmniCloud RL Environment Wrapper
Terminal Bench v2 - Multi-Cloud Infrastructure Orchestration Platform

This environment provides an interface for RL agents to interact with
a buggy microservices infrastructure platform. The agent must identify and fix
120 interconnected bugs across 15 services.

Usage:
    # With Docker (recommended)
    docker compose up -d  # Start all services
    docker compose -f docker-compose.test.yml up --build  # Run tests

    # Environment API
    from environment import OmniCloudEnvironment

    env = OmniCloudEnvironment(max_steps=300)
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


class OmniCloudEnvironment:
    """
    RL Environment for the OmniCloud multi-cloud infrastructure orchestration platform.

    This environment wraps a buggy microservices codebase with 120 intentional bugs.
    The agent's goal is to fix all bugs and get all 750+ tests passing.

    Attributes:
        max_steps: Maximum number of steps before truncation
        project_root: Root directory of the OmniCloud project
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
                    "errors": {"type": "list_str", "description": "Error messages (up to 15)"},
                    "raw_output": {"type": "str", "description": "Raw pytest output (up to 15000 chars)"},
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
        "services/gateway/": [
            "tests/integration/test_service_communication.py",
            "tests/security/test_vulnerabilities.py",
        ],
        "services/auth/": [
            "tests/security/test_vulnerabilities.py",
            "tests/chaos/test_multi_tenancy.py",
        ],
        "services/tenants/": [
            "tests/chaos/test_multi_tenancy.py",
            "tests/unit/test_billing_metering.py",
        ],
        "services/compute/": [
            "tests/unit/test_resource_scheduling.py",
            "tests/unit/test_infrastructure_state.py",
        ],
        "services/network/": [
            "tests/unit/test_network_management.py",
            "tests/security/test_vulnerabilities.py",
        ],
        "services/storage/": [
            "tests/unit/test_infrastructure_state.py",
            "tests/security/test_vulnerabilities.py",
        ],
        "services/dns/": [
            "tests/unit/test_network_management.py",
        ],
        "services/loadbalancer/": [
            "tests/unit/test_network_management.py",
            "tests/unit/test_resource_scheduling.py",
        ],
        "services/secrets/": [
            "tests/security/test_vulnerabilities.py",
            "tests/system/test_end_to_end.py",
        ],
        "services/config/": [
            "tests/system/test_end_to_end.py",
        ],
        "services/deploy/": [
            "tests/integration/test_deployment_pipeline.py",
            "tests/system/test_end_to_end.py",
        ],
        "services/monitor/": [
            "tests/integration/test_service_communication.py",
            "tests/performance/test_provisioning.py",
        ],
        "services/billing/": [
            "tests/unit/test_billing_metering.py",
            "tests/chaos/test_multi_tenancy.py",
        ],
        "services/audit/": [
            "tests/integration/test_service_communication.py",
        ],
        "services/compliance/": [
            "tests/security/test_vulnerabilities.py",
            "tests/system/test_end_to_end.py",
        ],
        "shared/clients/": [
            "tests/integration/test_service_communication.py",
            "tests/chaos/test_distributed_consensus.py",
        ],
        "shared/events/": [
            "tests/chaos/test_distributed_consensus.py",
            "tests/integration/test_service_communication.py",
        ],
        "shared/utils/": [
            "tests/unit/test_infrastructure_state.py",
            "tests/chaos/test_distributed_consensus.py",
            "tests/security/test_vulnerabilities.py",
        ],
        "shared/infra/": [
            "tests/unit/test_infrastructure_state.py",
            "tests/chaos/test_distributed_consensus.py",
            "tests/unit/test_resource_scheduling.py",
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
                timeout=600,
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
                "errors": errors[:15],
                "raw_output": output[:15000],
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
                timeout=180,
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
                "errors": errors[:15],
                "raw_output": output[:15000],
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
            'L1': 'Circular imports across shared modules - ImportError on startup',
            'L2': 'Missing tenant migration files - MigrationError on DB init',
            'L3': 'Kafka auto.create.topics.enable disabled - TopicNotFound on publish',
            'L4': 'Database migration ordering wrong between services - dependency error',
            'L5': 'Service startup order dependency - ConnectionRefused from gateway',
            'L6': 'Consul ACL bootstrap not completed - unauthorized on registration',
            'L7': 'etcd connection string uses https instead of http - TLS handshake fail',
            'L8': 'Vault auto-unseal not configured - sealed vault on restart',
            'L9': 'MinIO bucket creation race condition - NoSuchBucket on upload',
            'L10': 'Celery broker URL uses wrong Redis database number - connection fail',
            'L11': 'CORS middleware blocks inter-service calls - 403 on internal requests',
            'L12': 'Schema validation library version conflict - AttributeError on import',
            'L13': 'Consul service registration missing health check URL - unhealthy forever',
            'L14': 'Worker registration uses wrong serializer format - deserialization error',
            'L15': 'Environment variable string "false" treated as truthy Python value',

            # Infrastructure State (A1-A12)
            'A1': 'State machine transition race - concurrent transitions corrupt state',
            'A2': 'Eventual consistency violation - reads return stale during convergence',
            'A3': 'Reconciliation loop runs infinitely - no max iteration bound',
            'A4': 'Desired vs actual state drift detection uses wrong comparison',
            'A5': 'Resource dependency graph cycle not detected - infinite planning loop',
            'A6': 'State lock contention deadlock - inconsistent lock ordering',
            'A7': 'Partial apply rollback incomplete - orphaned partial resources',
            'A8': 'State serialization version mismatch - deserialization failure on upgrade',
            'A9': 'Concurrent modification lost update - no optimistic concurrency control',
            'A10': 'Orphaned resource cleanup misses resources with dangling references',
            'A11': 'State snapshot corruption on concurrent writes - invalid restore point',
            'A12': 'Cross-region state sync lag unbounded - stale reads across regions',

            # Distributed Consensus (B1-B10)
            'B1': 'Leader election race condition - multiple leaders elected briefly',
            'B2': 'Split-brain during network partition - both partitions accept writes',
            'B3': 'Distributed lock stolen during long operation - lock TTL too short',
            'B4': 'Consensus quorum off-by-one - writes succeed with exactly half nodes',
            'B5': 'Version vector merge bug - lost updates during concurrent modifications',
            'B6': 'Gossip protocol message ordering - stale membership data propagated',
            'B7': 'etcd watch revision gap - missed updates between compaction events',
            'B8': 'Raft log compaction race - entries lost during snapshot creation',
            'B9': 'Membership change during election - inconsistent voter set',
            'B10': 'Snapshot transfer corruption - checksum not validated on receive',

            # Multi-Tenancy (C1-C8)
            'C1': 'Resource isolation bypass - missing tenant_id filter in ORM queries',
            'C2': 'Quota enforcement race - concurrent requests exceed quota atomically',
            'C3': 'Tenant scoping leak in queries - raw SQL missing WHERE tenant_id =',
            'C4': 'Cross-tenant data access via shared cache key without tenant prefix',
            'C5': 'Tenant deletion leaves orphaned resources in compute and network',
            'C6': 'Resource limit soft vs hard confusion - soft limit treated as hard',
            'C7': 'Tenant migration data loss - foreign key references not updated',
            'C8': 'Billing isolation miscalculation - shared resource cost split wrong',

            # Network Management (D1-D10)
            'D1': 'CIDR allocation overlap - no overlap check when allocating subnets',
            'D2': 'Firewall rule ordering conflict - rules applied in wrong priority order',
            'D3': 'VPN tunnel MTU mismatch - packets silently dropped over 1400 bytes',
            'D4': 'DNS resolution circular CNAME - infinite loop in resolver',
            'D5': 'Subnet exhaustion detected late - allocation succeeds when pool is full',
            'D6': 'Security group rule deduplication wrong - duplicate rules accepted',
            'D7': 'Route table propagation lag - packets routed to old destination',
            'D8': 'NAT gateway port allocation race - same port assigned twice',
            'D9': 'Load balancer health check flapping - rapid up/down transitions',
            'D10': 'Peering connection asymmetric routing - one direction fails silently',

            # Resource Scheduling (E1-E8)
            'E1': 'Bin packing over-commit - available capacity calculated with float imprecision',
            'E2': 'Affinity rule evaluation order wrong - later rules override earlier ones',
            'E3': 'Anti-affinity constraint race - two VMs placed on same host concurrently',
            'E4': 'Resource limit enforcement uses float comparison - precision loss',
            'E5': 'Spot instance preemption handling drops notification - ungraceful termination',
            'E6': 'Placement group capacity check wrong - off-by-one in available slots',
            'E7': 'Node drain race condition - new workload scheduled during drain',
            'E8': 'Resource reservation expiry not cleaned up - phantom reservations block allocation',

            # Deployment Pipeline (F1-F10)
            'F1': 'Rolling update batch size off-by-one - one extra instance in each batch',
            'F2': 'Blue-green switch race - both versions receive traffic briefly',
            'F3': 'Canary metric evaluation window too short - premature promotion',
            'F4': 'Rollback version selection wrong - rolls back to N-2 instead of N-1',
            'F5': 'Deployment lock stolen during long deploy - concurrent deploy corrupts state',
            'F6': 'Health check grace period not respected - instances marked unhealthy too early',
            'F7': 'Deployment dependency ordering wrong - dependent service deployed first',
            'F8': 'Parallel deploy resource conflict - shared resources corrupted',
            'F9': 'Deployment event ordering wrong - completion event before start event',
            'F10': 'Pre/post hooks execution order reversed - post-hook runs before deploy',

            # Database & Transactions (G1-G10)
            'G1': 'Cross-database transaction isolation - phantom reads across DBs',
            'G2': 'Connection pool exhaustion under load - no max pool limit enforcement',
            'G3': 'Saga compensation order wrong - resources freed in wrong sequence',
            'G4': 'Outbox pattern message loss - events deleted before publish confirmed',
            'G5': 'Read replica lag ignored - stale data served after write',
            'G6': 'Optimistic locking retry limit too low - updates silently dropped',
            'G7': 'Foreign key across databases - orphaned references not detected',
            'G8': 'Batch insert partial failure - half-committed batch on error',
            'G9': 'Index hint forces wrong query plan - full table scan on large tables',
            'G10': 'Deadlock from inconsistent lock ordering across services',

            # Billing & Metering (H1-H8)
            'H1': 'Usage metering clock skew across services - double counting',
            'H2': 'Proration calculation precision loss - float instead of Decimal',
            'H3': 'Invoice generation race - duplicate invoices for same billing period',
            'H4': 'Cost allocation tenant attribution wrong - shared costs split unevenly',
            'H5': 'Discount stacking order matters - applied in wrong sequence',
            'H6': 'Credit application timing wrong - credit applied after invoice finalized',
            'H7': 'Overage charge threshold off-by-one - charged at limit not above limit',
            'H8': 'Billing cycle boundary at midnight UTC - timezone edge case',

            # Security & Compliance (I1-I10)
            'I1': 'SQL injection in resource filter - user input in raw SQL query',
            'I2': 'SSRF via webhook URL validation - internal network accessible',
            'I3': 'Privilege escalation via role inheritance - transitive admin role',
            'I4': 'Rate limit bypass via X-Forwarded-For header spoofing',
            'I5': 'IDOR on tenant endpoints - missing ownership verification',
            'I6': 'Path traversal in artifact download - directory escape via ../../../',
            'I7': 'Mass assignment on resource update - hidden fields writable via API',
            'I8': 'Timing attack on API key comparison - early return reveals key length',
            'I9': 'Insecure default security group - all ingress allowed on creation',
            'I10': 'Compliance rule evaluation order - deny rules checked after allow',

            # Observability (J1-J7)
            'J1': 'Trace context lost across Kafka - broken distributed traces',
            'J2': 'Log correlation ID mismatch - request ID changes between services',
            'J3': 'Metrics cardinality explosion - unbounded label values from user input',
            'J4': 'Health check false positive - service reports healthy but dependency down',
            'J5': 'Error aggregation groups wrong - different errors lumped together',
            'J6': 'Alert deduplication window too short - duplicate alerts fire',
            'J7': 'Distributed tracing span not closed - memory leak in span collector',

            # Configuration (K1-K12)
            'K1': 'Template variable interpolation cycle - A references B references A',
            'K2': 'IaC plan vs apply drift - plan succeeds but apply creates different state',
            'K3': 'Environment variable precedence wrong - file overrides CLI args',
            'K4': 'Config version pinning race - concurrent version updates conflict',
            'K5': 'Secret reference resolution lazy vs eager - secret read at wrong time',
            'K6': 'Dependency graph topological sort wrong - non-deterministic ordering',
            'K7': 'Provider plugin version conflict - incompatible versions loaded',
            'K8': 'Resource default merge deep vs shallow - nested defaults lost',
            'K9': 'Output reference circular - output A depends on output B depends on A',
            'K10': 'Workspace isolation variable leak - workspace A sees workspace B vars',
            'K11': 'Conditional resource count boundary - count=0 still creates one resource',
            'K12': 'Dynamic block expansion order - blocks expanded in wrong sequence',
        }

    def get_setup_bugs(self) -> List[str]:
        """Get list of setup bug IDs that must be fixed first."""
        return ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'L8', 'L9', 'L10',
                'L11', 'L12', 'L13', 'L14', 'L15']

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
                'bugs': ['L5', 'L11', 'I4', 'J4'],
            },
            'auth': {
                'path': 'services/auth',
                'framework': 'Django',
                'port': 8001,
                'bugs': ['I3', 'I8', 'C1'],
            },
            'tenants': {
                'path': 'services/tenants',
                'framework': 'Django',
                'port': 8002,
                'bugs': ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'L2'],
            },
            'compute': {
                'path': 'services/compute',
                'framework': 'FastAPI',
                'port': 8003,
                'bugs': ['E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7', 'E8'],
            },
            'network': {
                'path': 'services/network',
                'framework': 'Django',
                'port': 8004,
                'bugs': ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10'],
            },
            'storage': {
                'path': 'services/storage',
                'framework': 'FastAPI',
                'port': 8005,
                'bugs': ['A7', 'I6'],
            },
            'dns': {
                'path': 'services/dns',
                'framework': 'Django',
                'port': 8006,
                'bugs': ['D4'],
            },
            'loadbalancer': {
                'path': 'services/loadbalancer',
                'framework': 'FastAPI',
                'port': 8007,
                'bugs': ['D9', 'E6'],
            },
            'secrets': {
                'path': 'services/secrets',
                'framework': 'Django',
                'port': 8008,
                'bugs': ['L8', 'K5'],
            },
            'config': {
                'path': 'services/config',
                'framework': 'Django',
                'port': 8009,
                'bugs': ['K1', 'K2', 'K3', 'K4', 'K6', 'K7', 'K8', 'K9', 'K10', 'K11', 'K12'],
            },
            'deploy': {
                'path': 'services/deploy',
                'framework': 'Celery/FastAPI',
                'port': 8010,
                'bugs': ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10'],
            },
            'monitor': {
                'path': 'services/monitor',
                'framework': 'FastAPI',
                'port': 8011,
                'bugs': ['J1', 'J2', 'J3', 'J5', 'J6', 'J7'],
            },
            'billing': {
                'path': 'services/billing',
                'framework': 'Django',
                'port': 8012,
                'bugs': ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8'],
            },
            'audit': {
                'path': 'services/audit',
                'framework': 'Django',
                'port': 8013,
                'bugs': ['J1', 'J2'],
            },
            'compliance': {
                'path': 'services/compliance',
                'framework': 'Django',
                'port': 8014,
                'bugs': ['I9', 'I10'],
            },
        }
