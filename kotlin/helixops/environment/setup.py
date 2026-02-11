"""
HelixOps RL Environment Setup
Distributed knowledge management platform - Apex-principal difficulty (1250 bugs, 12000+ tests)
Kotlin 1.9, Ktor 2.3, Exposed ORM, 10 Microservices, Kafka, PostgreSQL, Redis, Consul
"""

import os
import shlex
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .reward import (
    TestResult,
    RewardCalculator,
    parse_junit_reports_recursive,
    calculate_reward,
    BUG_TEST_MAPPING,
    BUG_CATEGORIES,
    SERVICE_BUG_MAP,
)


class HelixOpsEnvironment:
    """
    RL Environment for HelixOps - Distributed Knowledge Management Platform.

    Apex-principal difficulty: 1250 bugs, 12000+ tests
    Stack: Kotlin 1.9, Ktor 2.3, Exposed ORM, 10 Microservices,
           Kafka 3.6, PostgreSQL 16, Redis 7, Consul 1.17

    Modules: shared, gateway, auth, documents, search, graph,
             embeddings, collab, billing, notifications, analytics
    """

    observation_space = {
        "type": "dict",
        "spaces": {
            "file_content": {"type": "text", "max_length": 100000},
            "test_results": {"type": "text", "max_length": 50000},
            "command_output": {"type": "text", "max_length": 50000},
            "current_step": {"type": "int", "min": 0, "max": 400},
            "files_changed": {"type": "list", "max_length": 200},
        },
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
        },
    }

    _SERVICE_MODULE_MAP = {
        "shared": "shared",
        "gateway": "gateway",
        "auth": "auth",
        "documents": "documents",
        "search": "search",
        "graph": "graph",
        "embeddings": "embeddings",
        "collab": "collab",
        "billing": "billing",
        "notifications": "notifications",
        "analytics": "analytics",
    }

    _FILE_TEST_MAP = {
        # Shared
        "shared/src/main/kotlin/com/helixops/shared/config/AppConfig.kt": [
            "com.helixops.shared.ConfigTests",
        ],
        "shared/src/main/kotlin/com/helixops/shared/events/EventBus.kt": [
            "com.helixops.shared.EventBusTests",
        ],
        "shared/src/main/kotlin/com/helixops/shared/security/JwtProvider.kt": [
            "com.helixops.shared.SecurityTests",
        ],
        "shared/src/main/kotlin/com/helixops/shared/serialization/SerializationConfig.kt": [
            "com.helixops.shared.SerializationTests",
        ],
        # Gateway
        "gateway/src/main/kotlin/com/helixops/gateway/GatewayApplication.kt": [
            "com.helixops.gateway.GatewayTests",
        ],
        "gateway/src/main/kotlin/com/helixops/gateway/routes/ApiRoutes.kt": [
            "com.helixops.gateway.GatewayTests",
        ],
        # Auth
        "auth/src/main/kotlin/com/helixops/auth/AuthService.kt": [
            "com.helixops.auth.AuthTests",
        ],
        "auth/src/main/kotlin/com/helixops/auth/JwtValidator.kt": [
            "com.helixops.auth.AuthTests",
        ],
        # Documents
        "documents/src/main/kotlin/com/helixops/documents/DocumentService.kt": [
            "com.helixops.documents.DocumentTests",
        ],
        "documents/src/main/kotlin/com/helixops/documents/repository/DocumentRepository.kt": [
            "com.helixops.documents.DocumentTests",
        ],
        # Search
        "search/src/main/kotlin/com/helixops/search/SearchService.kt": [
            "com.helixops.search.SearchTests",
        ],
        "search/src/main/kotlin/com/helixops/search/QueryParser.kt": [
            "com.helixops.search.SearchTests",
        ],
        # Graph
        "graph/src/main/kotlin/com/helixops/graph/GraphService.kt": [
            "com.helixops.graph.GraphTests",
        ],
        "graph/src/main/kotlin/com/helixops/graph/repository/GraphRepository.kt": [
            "com.helixops.graph.GraphTests",
        ],
        # Embeddings
        "embeddings/src/main/kotlin/com/helixops/embeddings/EmbeddingService.kt": [
            "com.helixops.embeddings.EmbeddingTests",
        ],
        "embeddings/src/main/kotlin/com/helixops/embeddings/VectorStore.kt": [
            "com.helixops.embeddings.EmbeddingTests",
        ],
        # Collab
        "collab/src/main/kotlin/com/helixops/collab/CollabService.kt": [
            "com.helixops.collab.CollabTests",
        ],
        "collab/src/main/kotlin/com/helixops/collab/WebSocketHandler.kt": [
            "com.helixops.collab.CollabTests",
        ],
        # Billing
        "billing/src/main/kotlin/com/helixops/billing/BillingService.kt": [
            "com.helixops.billing.BillingTests",
        ],
        "billing/src/main/kotlin/com/helixops/billing/InvoiceCalculator.kt": [
            "com.helixops.billing.BillingTests",
        ],
        # Notifications
        "notifications/src/main/kotlin/com/helixops/notifications/NotificationService.kt": [
            "com.helixops.notifications.NotificationTests",
        ],
        "notifications/src/main/kotlin/com/helixops/notifications/Dispatcher.kt": [
            "com.helixops.notifications.NotificationTests",
        ],
        # Analytics
        "analytics/src/main/kotlin/com/helixops/analytics/AnalyticsService.kt": [
            "com.helixops.analytics.AnalyticsTests",
        ],
        "analytics/src/main/kotlin/com/helixops/analytics/MetricsCollector.kt": [
            "com.helixops.analytics.AnalyticsTests",
        ],
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
        return self._get_observation(
            "Environment reset. HelixOps has 1250 bugs to fix across 10 microservices."
        )

    def step(self, action: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        if self.done:
            return self._get_observation("Episode is done."), 0.0, True, {}
        self.current_step += 1
        self.done = self.current_step >= self.max_steps
        action_type = action.get("type", "")
        validation_error = self.validate_action(action)
        if validation_error:
            return (
                self._get_observation(f"Invalid action: {validation_error}"),
                -0.01,
                self.done,
                {"error": validation_error},
            )
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
            if not file_path:
                return "Invalid file_path"
            if ".." in file_path or file_path.startswith("/"):
                return "Path traversal not allowed"
            resolved = (self.project_dir / file_path).resolve()
            if not str(resolved).startswith(str(self.project_dir.resolve())):
                return "Path escapes project directory"
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
            content = (
                content.replace(old_content, new_content, 1)
                if old_content
                else new_content
            )
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
                action["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.project_dir),
            )
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
            module = parts[0] if len(parts) > 0 else ""
            results.extend(self._run_targeted_tests_by_class(tc, module))
        return results

    def _run_targeted_tests_by_class(self, test_class, module=""):
        if module and module in self._SERVICE_MODULE_MAP:
            gradle_module = self._SERVICE_MODULE_MAP[module]
            cmd = (
                f'./gradlew :{gradle_module}:test '
                f'--tests "{test_class}" --no-daemon'
            )
        else:
            cmd = f'./gradlew test --tests "{test_class}" --no-daemon'
        try:
            subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.project_dir),
            )
            return parse_junit_reports_recursive(self.project_dir)
        except Exception:
            return []

    def _run_tests(self):
        try:
            subprocess.run(
                ["./gradlew", "test", "--no-daemon"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.project_dir),
            )
            return parse_junit_reports_recursive(self.project_dir)
        except Exception:
            return []

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
        subprocess.run(
            ["git", "checkout", "."],
            cwd=self.project_dir,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "clean", "-fd"],
            cwd=self.project_dir,
            capture_output=True,
            timeout=30,
        )
        # Clean Gradle build artifacts for all modules
        for module in self._SERVICE_MODULE_MAP.values():
            build_dir = self.project_dir / module / "build"
            if build_dir.exists():
                shutil.rmtree(build_dir, ignore_errors=True)
        # Clean root build dir
        root_build = self.project_dir / "build"
        if root_build.exists():
            shutil.rmtree(root_build, ignore_errors=True)
