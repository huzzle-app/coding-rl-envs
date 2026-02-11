"""
VertexGrid RL Environment Setup
Real-time fleet management platform - Apex-principal difficulty (1250 bugs, 12000+ tests)
Java 21, 10 Spring Boot Microservices, Kafka, PostgreSQL, Redis, Consul
"""

import os
import shlex
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TestResult:
    name: str
    passed: bool
    duration: float = 0.0
    category: str = "unit"
    bug_markers: List[str] = field(default_factory=list)
    error_message: str = ""
    service: str = ""


class VertexGridEnvironment:
    """
    RL Environment for VertexGrid - Real-time Fleet Management Platform.

    Apex-principal difficulty: 1250 bugs, 12000+ tests
    Stack: Java 21, 10 Spring Boot Microservices, Kafka, PostgreSQL, Redis, Consul
    """

    observation_space = {
        "type": "dict",
        "spaces": {
            "file_content": {"type": "text", "max_length": 100000},
            "test_results": {"type": "text", "max_length": 50000},
            "command_output": {"type": "text", "max_length": 50000},
            "current_step": {"type": "int", "min": 0, "max": 400},
            "files_changed": {"type": "list", "max_length": 200},
        }
    }

    action_space = {
        "type": "dict",
        "actions": {
            "edit": {
                "file_path": {"type": "string", "max_length": 500},
                "old_content": {"type": "string", "max_length": 10000},
                "new_content": {"type": "string", "max_length": 10000},
            },
            "read": {
                "file_path": {"type": "string", "max_length": 500},
            },
            "run_command": {
                "command": {"type": "string", "max_length": 1000},
            },
            "run_tests": {
                "test_class": {"type": "string", "max_length": 200},
                "module": {"type": "string", "max_length": 100},
            },
        }
    }

    _FILE_TEST_MAP = {
        # Shared module
        "shared/src/main/java/com/vertexgrid/shared/config/AppConfig.java": [
            "com.vertexgrid.shared.ConfigTest"
        ],
        "shared/src/main/java/com/vertexgrid/shared/config/KafkaConfig.java": [
            "com.vertexgrid.shared.KafkaConfigTest"
        ],
        "shared/src/main/java/com/vertexgrid/shared/concurrency/VirtualThreadExecutor.java": [
            "com.vertexgrid.shared.ConcurrencyTest"
        ],
        "shared/src/main/java/com/vertexgrid/shared/util/CollectionUtils.java": [
            "com.vertexgrid.shared.CollectionUtilsTest"
        ],
        "shared/src/main/java/com/vertexgrid/shared/security/JwtTokenProvider.java": [
            "com.vertexgrid.shared.SecurityTest"
        ],
        "shared/src/main/java/com/vertexgrid/shared/event/EventBus.java": [
            "com.vertexgrid.shared.EventBusTest"
        ],
        "shared/src/main/java/com/vertexgrid/shared/event/EventStore.java": [
            "com.vertexgrid.shared.EventStoreTest"
        ],
        "shared/src/main/java/com/vertexgrid/shared/util/MdcPropagator.java": [
            "com.vertexgrid.shared.ObservabilityTest"
        ],
        "shared/src/main/java/com/vertexgrid/shared/util/MetricsCollector.java": [
            "com.vertexgrid.shared.ObservabilityTest"
        ],
        # Gateway
        "gateway/src/main/java/com/vertexgrid/gateway/service/RequestService.java": [
            "com.vertexgrid.gateway.RequestServiceTest"
        ],
        "gateway/src/main/java/com/vertexgrid/gateway/controller/GatewayController.java": [
            "com.vertexgrid.gateway.SecurityTest"
        ],
        # Auth
        "auth/src/main/java/com/vertexgrid/auth/service/AuthenticationService.java": [
            "com.vertexgrid.auth.AuthServiceTest"
        ],
        "auth/src/main/java/com/vertexgrid/auth/security/TokenValidator.java": [
            "com.vertexgrid.auth.TokenValidatorTest"
        ],
        # Vehicles
        "vehicles/src/main/java/com/vertexgrid/vehicles/service/VehicleService.java": [
            "com.vertexgrid.vehicles.VehicleServiceTest"
        ],
        "vehicles/src/main/java/com/vertexgrid/vehicles/model/Vehicle.java": [
            "com.vertexgrid.vehicles.VehicleModelTest"
        ],
        # Routes
        "routes/src/main/java/com/vertexgrid/routes/service/RouteService.java": [
            "com.vertexgrid.routes.RouteServiceTest"
        ],
        "routes/src/main/java/com/vertexgrid/routes/service/GeofenceService.java": [
            "com.vertexgrid.routes.RouteServiceTest"
        ],
        # Dispatch
        "dispatch/src/main/java/com/vertexgrid/dispatch/service/DispatchService.java": [
            "com.vertexgrid.dispatch.DispatchServiceTest"
        ],
        "dispatch/src/main/java/com/vertexgrid/dispatch/model/JobAssignment.java": [
            "com.vertexgrid.dispatch.DispatchServiceTest"
        ],
        # Tracking
        "tracking/src/main/java/com/vertexgrid/tracking/service/TrackingService.java": [
            "com.vertexgrid.tracking.TrackingServiceTest"
        ],
        # Billing
        "billing/src/main/java/com/vertexgrid/billing/service/InvoiceService.java": [
            "com.vertexgrid.billing.BillingServiceTest"
        ],
        "billing/src/main/java/com/vertexgrid/billing/service/PaymentService.java": [
            "com.vertexgrid.billing.BillingServiceTest"
        ],
        # Analytics
        "analytics/src/main/java/com/vertexgrid/analytics/service/AnalyticsService.java": [
            "com.vertexgrid.analytics.AnalyticsServiceTest"
        ],
        # Notifications
        "notifications/src/main/java/com/vertexgrid/notifications/service/NotificationService.java": [
            "com.vertexgrid.notifications.NotificationServiceTest"
        ],
        # Compliance
        "compliance/src/main/java/com/vertexgrid/compliance/service/ComplianceService.java": [
            "com.vertexgrid.compliance.ComplianceServiceTest"
        ],
    }

    # Maps services to their modules for targeted test execution
    _SERVICE_MODULE_MAP = {
        "shared": "shared",
        "gateway": "gateway",
        "auth": "auth",
        "vehicles": "vehicles",
        "routes": "routes",
        "dispatch": "dispatch",
        "tracking": "tracking",
        "billing": "billing",
        "analytics": "analytics",
        "notifications": "notifications",
        "compliance": "compliance",
    }

    def __init__(self, max_steps: int = 200, timeout: int = 600, full_run_interval: int = 5):
        self.max_steps = max_steps
        self.timeout = timeout
        self.full_run_interval = full_run_interval
        self.project_dir = Path(__file__).parent.parent
        self.current_step = 0
        self.files_changed: List[str] = []
        self.test_results: List[TestResult] = []
        self.initial_test_results: List[TestResult] = []
        self.mutating_steps = 0
        self.done = False

    def reset(self) -> Dict[str, Any]:
        self._restore_initial_state()
        self.current_step = 0
        self.files_changed = []
        self.test_results = []
        self.mutating_steps = 0
        self.done = False
        self.initial_test_results = self._run_tests()
        self.test_results = list(self.initial_test_results)
        return self._get_observation("Environment reset. VertexGrid has 1250 bugs to fix across 10 microservices.")

    def step(self, action: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        if self.done:
            return self._get_observation("Episode is done."), 0.0, True, {}
        self.current_step += 1
        self.done = self.current_step >= self.max_steps
        action_type = action.get("type", "")
        validation_error = self.validate_action(action)
        if validation_error:
            return self._get_observation(f"Invalid action: {validation_error}"), -0.01, self.done, {"error": validation_error}
        if action_type == "edit":
            result = self._handle_edit(action)
            self.mutating_steps += 1
        elif action_type == "read":
            result = self._handle_read(action)
        elif action_type == "run_command":
            result = self._handle_run_command(action)
        elif action_type == "run_tests":
            result = self._handle_run_tests(action)
        else:
            result = f"Unknown action type: {action_type}"
        if action_type == "edit" and self.mutating_steps % self.full_run_interval == 0:
            self.test_results = self._run_tests()
        # Check all-tests-pass done condition after full run
        is_full_run = (action_type == "edit" and self.mutating_steps % self.full_run_interval == 0) or action_type == "run_tests"
        if is_full_run and len(self.test_results) > 0 and all(r.passed for r in self.test_results):
            self.done = True
        from .reward import calculate_reward
        reward_info = calculate_reward(self.test_results, self.initial_test_results)
        reward = reward_info["reward"]
        info = {
            "step": self.current_step,
            "tests_passed": reward_info["tests_passed"],
            "tests_total": reward_info["tests_total"],
            "pass_rate": reward_info["pass_rate"],
            "bugs_fixed": reward_info["bugs_fixed"],
            "reward_breakdown": reward_info,
        }
        return self._get_observation(result), reward, self.done, info

    def validate_action(self, action: Dict[str, Any]) -> Optional[str]:
        action_type = action.get("type", "")
        if action_type not in ("edit", "read", "run_command", "run_tests"):
            return f"Invalid action type: {action_type}"
        if action_type == "edit":
            file_path = action.get("file_path", "")
            if not file_path:
                return "file_path required"
            if ".." in file_path or file_path.startswith("/"):
                return "Path traversal not allowed"
            resolved = (self.project_dir / file_path).resolve()
            if not str(resolved).startswith(str(self.project_dir.resolve())):
                return "Path escapes project directory"
            if file_path.startswith("src/test/") or "/src/test/" in file_path:
                return "Editing test files is not allowed"
            if len(action.get("new_content", "")) > 10000:
                return "Content too large"
        if action_type == "read":
            file_path = action.get("file_path", "")
            if not file_path or ".." in file_path or file_path.startswith("/"):
                return "Invalid file_path"
            resolved = (self.project_dir / file_path).resolve()
            if not str(resolved).startswith(str(self.project_dir.resolve())):
                return "Path escapes project directory"
        if action_type == "run_command":
            cmd = action.get("command", "")
            try:
                args = shlex.split(cmd)
            except ValueError:
                return "Invalid command syntax"
            if not args:
                return "Empty command"
            safe_commands = {'mvn', 'cat', 'ls', 'grep', 'find', 'head', 'tail', 'wc'}
            if args[0] not in safe_commands:
                return f"Command not allowed: {args[0]}"
        return None

    def _handle_edit(self, action):
        file_path = action["file_path"]
        full_path = (self.project_dir / file_path).resolve()
        if not str(full_path).startswith(str(self.project_dir.resolve())):
            return "Path escapes project directory"
        if not full_path.exists():
            return f"File not found: {file_path}"
        try:
            content = full_path.read_text()
            old_content = action.get("old_content", "")
            new_content = action.get("new_content", "")
            if old_content and old_content not in content:
                return f"old_content not found in {file_path}"
            content = content.replace(old_content, new_content, 1) if old_content else new_content
            full_path.write_text(content)
            self.files_changed.append(file_path)
            targeted = self._run_targeted_tests(file_path)
            return f"File edited: {file_path}. {len(targeted)} targeted tests run."
        except Exception as e:
            return f"Edit failed: {e}"

    def _handle_read(self, action):
        file_path = action["file_path"]
        full_path = (self.project_dir / file_path).resolve()
        if not str(full_path).startswith(str(self.project_dir.resolve())):
            return "Path escapes project directory"
        if not full_path.exists():
            return f"File not found: {file_path}"
        try:
            content = full_path.read_text()
            return content[:100000]
        except Exception as e:
            return f"Read failed: {e}"

    def _handle_run_command(self, action):
        try:
            args = shlex.split(action["command"])
        except ValueError as e:
            return f"Invalid command syntax: {e}"
        if not args:
            return "Empty command"
        safe_commands = {'mvn', 'cat', 'ls', 'grep', 'find', 'head', 'tail', 'wc'}
        if args[0] not in safe_commands:
            return f"Command not allowed: {args[0]}"
        try:
            result = subprocess.run(
                args, shell=False, capture_output=True, text=True,
                timeout=self.timeout, cwd=str(self.project_dir))
            output = result.stdout + result.stderr
            return output[:50000]
        except subprocess.TimeoutExpired:
            return "Command timed out"
        except Exception as e:
            return f"Command failed: {e}"

    def _handle_run_tests(self, action):
        test_class = action.get("test_class", "")
        module = action.get("module", "")
        if test_class:
            results = self._run_targeted_tests_by_class(test_class, module)
        else:
            results = self._run_tests()
            self.test_results = results
        passed = sum(1 for r in results if r.passed)
        return f"Tests: {passed}/{len(results)} passed"

    def _run_targeted_tests(self, file_path):
        test_classes = self._FILE_TEST_MAP.get(file_path, [])
        results = []
        for tc in test_classes:
            # Determine module from file path
            parts = file_path.split("/")
            module = parts[0] if parts else ""
            results.extend(self._run_targeted_tests_by_class(tc, module))
        return results

    def _run_targeted_tests_by_class(self, test_class, module=""):
        simple_name = test_class.split(".")[-1]
        args = ['mvn', 'test', f'-Dtest={simple_name}', '-Dsurefire.useFile=true', '-q']
        if module:
            args = ['mvn', 'test', '-pl', module, f'-Dtest={simple_name}', '-Dsurefire.useFile=true', '-q']
        try:
            subprocess.run(args, shell=False, capture_output=True, text=True,
                          timeout=self.timeout, cwd=str(self.project_dir))
            return self._parse_surefire_reports(filter_class=test_class, module=module)
        except Exception:
            return []

    def _run_tests(self):
        try:
            subprocess.run(['mvn', 'test', '-Dsurefire.useFile=true', '-q'],
                          shell=False, capture_output=True, text=True,
                          timeout=self.timeout, cwd=str(self.project_dir))
            return self._parse_surefire_reports()
        except Exception:
            return []

    def _parse_surefire_reports(self, filter_class=None, module=None):
        results = []
        # Search all module target directories for surefire reports
        search_dirs = []
        if module:
            search_dirs.append(self.project_dir / module / 'target' / 'surefire-reports')
        else:
            for mod in self._SERVICE_MODULE_MAP.values():
                report_dir = self.project_dir / mod / 'target' / 'surefire-reports'
                if report_dir.exists():
                    search_dirs.append(report_dir)

        for report_dir in search_dirs:
            if not report_dir.exists():
                continue
            for xml_file in report_dir.glob('TEST-*.xml'):
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    for testcase in root.findall('testcase'):
                        classname = testcase.get('classname', '')
                        if filter_class and classname != filter_class:
                            continue
                        name = testcase.get('name', '')
                        time_val = float(testcase.get('time', '0'))
                        failure = testcase.find('failure')
                        error = testcase.find('error')
                        skipped = testcase.find('skipped')
                        if skipped is not None:
                            continue
                        passed = failure is None and error is None
                        error_msg = ""
                        if failure is not None:
                            error_msg = failure.get('message', '') or failure.text or ''
                        elif error is not None:
                            error_msg = error.get('message', '') or error.text or ''
                        # Determine service from classname
                        service = self._get_service_from_classname(classname)
                        results.append(TestResult(
                            name=name, passed=passed, duration=time_val,
                            category=self._categorize_test(classname),
                            bug_markers=self._get_bug_markers(name),
                            error_message=error_msg[:500] if error_msg else "",
                            service=service
                        ))
                except ET.ParseError:
                    continue
        return results

    def _categorize_test(self, classname):
        lower = classname.lower()
        if 'concurrency' in lower or 'thread' in lower:
            return 'concurrency'
        elif 'security' in lower:
            return 'security'
        elif 'integration' in lower:
            return 'integration'
        elif 'performance' in lower or 'perf' in lower:
            return 'performance'
        elif 'chaos' in lower:
            return 'chaos'
        elif 'system' in lower or 'e2e' in lower:
            return 'system'
        return 'unit'

    def _get_service_from_classname(self, classname):
        for service in self._SERVICE_MODULE_MAP:
            if f'.{service}.' in classname:
                return service
        return 'shared'

    def _get_bug_markers(self, test_name):
        from .reward import BUG_TEST_MAPPING
        return [bug_id for bug_id, tests in BUG_TEST_MAPPING.items() if test_name in tests]

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
        # Clean Maven build artifacts across all modules
        for mod in self._SERVICE_MODULE_MAP.values():
            target_dir = self.project_dir / mod / 'target'
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)

    def gym_step(self, action: Dict[str, Any]):
        """Gymnasium-compatible step returning (obs, reward, done, truncated, info)."""
        obs, reward, done, info = self.step(action)
        truncated = self.current_step >= self.max_steps and not all(
            r.passed for r in self.test_results
        ) if self.test_results else self.current_step >= self.max_steps
        return obs, reward, done, truncated, info

    def _get_observation(self, result):
        passed = sum(1 for r in self.test_results if r.passed)
        total = len(self.test_results)
        test_summary = f"Tests: {passed}/{total} passed\n"
        for r in self.test_results[:100]:
            status = "PASS" if r.passed else "FAIL"
            test_summary += f"  [{status}] [{r.service}] {r.name}"
            if not r.passed and r.error_message:
                test_summary += f" - {r.error_message[:80]}"
            test_summary += "\n"
        if total > 100:
            test_summary += f"  ... and {total - 100} more tests\n"
        return {
            "file_content": result[:100000] if result else "",
            "test_results": test_summary[:50000],
            "command_output": "",
            "current_step": self.current_step,
            "files_changed": self.files_changed[-200:],
        }
