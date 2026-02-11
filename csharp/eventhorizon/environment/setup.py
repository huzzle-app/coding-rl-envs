"""
EventHorizon RL Environment Setup
Distributed event ticketing platform - Principal difficulty (75 bugs, 510+ tests)
C# 12, .NET 8, 10 ASP.NET Core Microservices, RabbitMQ, PostgreSQL, Redis, Consul
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


class EventHorizonEnvironment:
    """
    RL Environment for EventHorizon - Distributed Event Ticketing Platform.

    Principal difficulty: 75 bugs, 510+ tests
    Stack: C# 12, .NET 8, 10 ASP.NET Core Microservices, RabbitMQ, PostgreSQL, Redis, Consul
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
        # Shared
        "src/Shared/Config/ServiceCollectionExtensions.cs": ["EventHorizon.Shared.Tests.ConfigTests"],
        "src/Shared/Config/RabbitMqConfig.cs": ["EventHorizon.Shared.Tests.ConfigTests"],
        "src/Shared/Security/JwtTokenProvider.cs": ["EventHorizon.Shared.Tests.SecurityTests"],
        "src/Shared/Events/EventBus.cs": ["EventHorizon.Shared.Tests.EventBusTests"],
        "src/Shared/Events/OutboxProcessor.cs": ["EventHorizon.Shared.Tests.EventBusTests"],
        "src/Shared/Models/Money.cs": ["EventHorizon.Shared.Tests.ModelTests"],
        "src/Shared/Models/TicketStatus.cs": ["EventHorizon.Shared.Tests.ModelTests"],
        # Gateway
        "src/Gateway/Controllers/GatewayController.cs": ["EventHorizon.Gateway.Tests.GatewayTests"],
        "src/Gateway/Services/RateLimiterService.cs": ["EventHorizon.Gateway.Tests.GatewayTests"],
        # Auth
        "src/Auth/Services/AuthService.cs": ["EventHorizon.Auth.Tests.AuthTests"],
        "src/Auth/Controllers/AuthController.cs": ["EventHorizon.Auth.Tests.AuthTests"],
        # Events
        "src/Events/Services/EventManagementService.cs": ["EventHorizon.Events.Tests.EventTests"],
        "src/Events/Controllers/EventController.cs": ["EventHorizon.Events.Tests.EventTests"],
        # Tickets
        "src/Tickets/Services/TicketInventoryService.cs": ["EventHorizon.Tickets.Tests.TicketTests"],
        "src/Tickets/Services/SeatMapService.cs": ["EventHorizon.Tickets.Tests.TicketTests"],
        # Orders
        "src/Orders/Services/OrderService.cs": ["EventHorizon.Orders.Tests.OrderTests"],
        "src/Orders/Services/OrderSagaService.cs": ["EventHorizon.Orders.Tests.OrderTests"],
        # Payments
        "src/Payments/Services/PaymentService.cs": ["EventHorizon.Payments.Tests.PaymentTests"],
        "src/Payments/Services/RefundService.cs": ["EventHorizon.Payments.Tests.PaymentTests"],
        # Venues
        "src/Venues/Services/VenueService.cs": ["EventHorizon.Venues.Tests.VenueTests"],
        "src/Venues/Controllers/VenueController.cs": ["EventHorizon.Venues.Tests.VenueTests"],
        # Notifications
        "src/Notifications/Hubs/NotificationHub.cs": ["EventHorizon.Notifications.Tests.NotificationTests"],
        "src/Notifications/Services/NotificationService.cs": ["EventHorizon.Notifications.Tests.NotificationTests"],
        # Analytics
        "src/Analytics/Services/AnalyticsService.cs": ["EventHorizon.Analytics.Tests.AnalyticsTests"],
        "src/Analytics/Controllers/AnalyticsController.cs": ["EventHorizon.Analytics.Tests.AnalyticsTests"],
        # Search
        "src/Search/Services/SearchService.cs": ["EventHorizon.Search.Tests.SearchTests"],
        "src/Search/Controllers/SearchController.cs": ["EventHorizon.Search.Tests.SearchTests"],
    }

    _SERVICE_MODULE_MAP = {
        "shared": "Shared",
        "gateway": "Gateway",
        "auth": "Auth",
        "events": "Events",
        "tickets": "Tickets",
        "orders": "Orders",
        "payments": "Payments",
        "venues": "Venues",
        "notifications": "Notifications",
        "analytics": "Analytics",
        "search": "Search",
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
        return self._get_observation("Environment reset. EventHorizon has 75 bugs to fix across 10 microservices.")

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
            if file_path.startswith("Tests/") or ".Tests/" in file_path or file_path.endswith("Test.cs") or file_path.endswith("Tests.cs"):
                return "Editing test files is not allowed"
            if len(action.get("new_content", "")) > 10000:
                return "Content too large"
        if action_type == "read":
            file_path = action.get("file_path", "")
            if not file_path or ".." in file_path or file_path.startswith("/"):
                return "Invalid file_path"
        if action_type == "run_command":
            cmd = action.get("command", "")
            for d in ["rm -rf", "mkfs", "dd if=", "> /dev/"]:
                if d in cmd:
                    return f"Dangerous command: {d}"
        return None

    def _handle_edit(self, action):
        file_path = action["file_path"]
        full_path = self.project_dir / file_path
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
        full_path = self.project_dir / file_path
        if not full_path.exists():
            return f"File not found: {file_path}"
        try:
            content = full_path.read_text()
            return content[:100000]
        except Exception as e:
            return f"Read failed: {e}"

    def _handle_run_command(self, action):
        try:
            result = subprocess.run(
                action["command"], shell=True, capture_output=True, text=True,
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
            parts = file_path.split("/")
            module = parts[1] if len(parts) > 1 else ""
            results.extend(self._run_targeted_tests_by_class(tc, module))
        return results

    def _run_targeted_tests_by_class(self, test_class, module=""):
        simple_name = test_class.split(".")[-1]
        test_project = f"tests/{module}.Tests" if module else ""
        if test_project:
            cmd = f'dotnet test {test_project} --filter "FullyQualifiedName~{test_class}" --logger "trx;LogFileName=targeted.trx" --no-build -q'
        else:
            cmd = f'dotnet test --filter "FullyQualifiedName~{test_class}" --logger "trx;LogFileName=targeted.trx" --no-build -q'
        try:
            subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=self.timeout, cwd=str(self.project_dir))
            return self._parse_trx_reports(filter_class=test_class, module=module)
        except Exception:
            return []

    def _run_tests(self):
        try:
            subprocess.run(
                'dotnet test --logger "trx;LogFileName=results.trx" -q',
                shell=True, capture_output=True, text=True,
                timeout=self.timeout, cwd=str(self.project_dir))
            return self._parse_trx_reports()
        except Exception:
            return []

    def _parse_trx_reports(self, filter_class=None, module=None):
        results = []
        search_dirs = []
        if module:
            test_dir = self.project_dir / 'tests' / f'{module}.Tests' / 'TestResults'
            if test_dir.exists():
                search_dirs.append(test_dir)
        else:
            for mod in self._SERVICE_MODULE_MAP.values():
                test_dir = self.project_dir / 'tests' / f'{mod}.Tests' / 'TestResults'
                if test_dir.exists():
                    search_dirs.append(test_dir)

        ns = {'vs': 'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
        for report_dir in search_dirs:
            for trx_file in report_dir.glob('*.trx'):
                try:
                    tree = ET.parse(trx_file)
                    root = tree.getroot()
                    for result_elem in root.findall('.//vs:UnitTestResult', ns):
                        test_name = result_elem.get('testName', '')
                        outcome = result_elem.get('outcome', 'Failed')
                        duration_str = result_elem.get('duration', '00:00:00')

                        if filter_class and filter_class not in test_name:
                            continue

                        passed = outcome == 'Passed'
                        error_msg = ""
                        if not passed:
                            output_elem = result_elem.find('.//vs:ErrorInfo/vs:Message', ns)
                            if output_elem is not None and output_elem.text:
                                error_msg = output_elem.text[:500]

                        service = self._get_service_from_testname(test_name)
                        results.append(TestResult(
                            name=test_name, passed=passed,
                            duration=0.0,
                            category=self._categorize_test(test_name),
                            bug_markers=self._get_bug_markers(test_name),
                            error_message=error_msg,
                            service=service
                        ))
                except ET.ParseError:
                    continue
        return results

    def _categorize_test(self, test_name):
        lower = test_name.lower()
        if 'concurrency' in lower or 'thread' in lower or 'async' in lower or 'deadlock' in lower:
            return 'concurrency'
        elif 'security' in lower or 'injection' in lower or 'jwt' in lower or 'traversal' in lower:
            return 'security'
        elif 'integration' in lower:
            return 'integration'
        return 'unit'

    def _get_service_from_testname(self, test_name):
        for service in self._SERVICE_MODULE_MAP:
            if f'.{service}.' in test_name.lower():
                return service
        return 'shared'

    def _get_bug_markers(self, test_name):
        from .reward import BUG_TEST_MAPPING
        return [bug_id for bug_id, tests in BUG_TEST_MAPPING.items() if test_name in tests]

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

    def _restore_initial_state(self):
        subprocess.run(['git', 'checkout', '.'], cwd=self.project_dir, capture_output=True, timeout=30)
        subprocess.run(['git', 'clean', '-fd'], cwd=self.project_dir, capture_output=True, timeout=30)
