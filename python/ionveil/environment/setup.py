"""IonVeil RL environment wrapper."""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .reward import sparse_reward, total_bugs, total_tests


@dataclass
class TestSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    targeted: bool = False
    output: str = ""


class IonVeilEnvironment:
    FILE_TEST_MAP = {
        "ionveil/__init__.py": ["tests/unit/models_test.py", "tests/unit/dispatch_test.py"],
        "ionveil/dispatch.py": ["tests/unit/dispatch_test.py", "tests/integration/mission_flow_test.py"],
        "ionveil/routing.py": ["tests/unit/routing_test.py", "tests/integration/mission_flow_test.py"],
        "ionveil/policy.py": ["tests/unit/policy_test.py", "tests/integration/security_pipeline_test.py"],
        "ionveil/security.py": ["tests/unit/security_test.py", "tests/integration/security_pipeline_test.py"],
        "ionveil/resilience.py": ["tests/unit/resilience_test.py", "tests/chaos/replay_chaos_test.py"],
        "ionveil/queue.py": ["tests/unit/queue_test.py"],
        "ionveil/statistics.py": ["tests/unit/statistics_test.py"],
        "ionveil/workflow.py": ["tests/unit/workflow_test.py", "tests/integration/mission_flow_test.py"],
        "ionveil/models.py": ["tests/unit/models_test.py"],
        "ionveil/scheduler.py": ["tests/unit/dispatch_test.py"],
        "ionveil/geo.py": ["tests/unit/routing_test.py"],
        "services/": ["tests/services/contracts_test.py"],
        "shared/": ["tests/services/contracts_test.py"],
        "migrations/": ["tests/services/contracts_test.py"],
    }

    SAFE_COMMANDS = {"python", "cat", "ls", "grep", "find", "head", "tail", "wc"}

    def __init__(self, work_dir: str):
        self.work_dir = Path(work_dir)
        self.max_steps = 340
        self.step_count = 0
        self.mutating_steps = 0
        self.full_run_interval = 5
        self.files_changed: List[str] = []
        self.last_test_summary = TestSummary()

    def _safe_path(self, rel: str) -> Path:
        if not rel or ".." in rel or rel.startswith("/"):
            raise ValueError("invalid path")
        target = (self.work_dir / rel).resolve()
        root = self.work_dir.resolve()
        if not target.is_relative_to(root):
            raise ValueError("path escapes workspace")
        return target

    def _validate_action(self, action: Dict[str, str]) -> None:
        action_type = action.get("type", "")
        if action_type not in {"edit", "read", "run_command"}:
            raise ValueError("unknown action type")

        if action_type in {"edit", "read"}:
            rel = action.get("file", "")
            self._safe_path(rel)
            if action_type == "edit":
                normalized = rel.replace("\\", "/")
                is_test_path = (
                    normalized.startswith("tests/")
                    or "/tests/" in normalized
                    or normalized.startswith("__tests__/")
                    or normalized.endswith("_test.py")
                    or normalized.endswith("_tests.py")
                    or normalized.endswith(".spec.py")
                )
                if is_test_path:
                    raise ValueError("editing test files is not allowed")

        if action_type == "run_command":
            args = shlex.split(action.get("command", ""))
            if not args:
                raise ValueError("empty command")
            if args[0] not in self.SAFE_COMMANDS:
                raise ValueError("command not allowed")

    def _run(self, command: str) -> str:
        args = shlex.split(command)
        proc = subprocess.run(args, cwd=self.work_dir, capture_output=True, text=True, check=False)
        return (proc.stdout or "") + (proc.stderr or "")

    def _edit(self, rel: str, content: str) -> str:
        target = self._safe_path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self.files_changed.append(rel)
        return "edit applied"

    def _read(self, rel: str) -> str:
        return self._safe_path(rel).read_text()

    def _tests_for_file(self, rel: str) -> List[str]:
        for prefix, tests in self.FILE_TEST_MAP.items():
            if rel.startswith(prefix):
                return tests
        return []

    @staticmethod
    def _parse_summary(output: str, targeted: bool) -> TestSummary:
        match = re.search(r"TB_SUMMARY\s+total=(\d+)\s+passed=(\d+)\s+failed=(\d+)\s+errors=(\d+)", output)
        if not match:
            return TestSummary(targeted=targeted, output=output)

        total = int(match.group(1))
        passed = int(match.group(2))
        failed = int(match.group(3)) + int(match.group(4))
        pass_rate = (passed / total) if total > 0 else 0.0
        return TestSummary(total=total, passed=passed, failed=failed, pass_rate=pass_rate, targeted=targeted, output=output)

    def _run_full_tests(self) -> TestSummary:
        output = self._run("python tests/run_all.py")
        return self._parse_summary(output, targeted=False)

    def _run_targeted_tests(self, rel: str) -> TestSummary:
        tests = self._tests_for_file(rel)
        if not tests:
            return TestSummary(targeted=True)
        output = self._run("python tests/run_all.py " + " ".join(tests))
        return self._parse_summary(output, targeted=True)

    def reset(self) -> Dict[str, Any]:
        self.step_count = 0
        self.mutating_steps = 0
        self.files_changed = []
        self.last_test_summary = self._run_full_tests()
        summary = self.last_test_summary
        return {
            "observation": {
                "action_result": "",
                "step": 0,
                "reward": 0.0,
                "test_summary": {
                    "total": summary.total,
                    "passed": summary.passed,
                    "failed": summary.failed,
                    "pass_rate": summary.pass_rate,
                    "targeted": summary.targeted,
                },
            },
            "reward": 0.0,
            "done": False,
            "info": {
                "step": 0,
                "max_steps": self.max_steps,
                "total_bugs": total_bugs(),
                "target_tests": total_tests(),
                "files_changed": [],
                "pass_rate": summary.pass_rate,
                "tests_total": summary.total,
                "tests_failed": summary.failed,
                "targeted_run": summary.targeted,
            },
        }

    def step(self, action: Dict[str, str]) -> Dict[str, Any]:
        self.step_count += 1

        try:
            self._validate_action(action)
        except ValueError as exc:
            return {
                "observation": {"action_result": "", "step": self.step_count},
                "reward": 0.0,
                "done": self.step_count >= self.max_steps,
                "info": {"error": str(exc), "step": self.step_count},
            }

        action_type = action["type"]
        result = ""
        run_error = None

        try:
            if action_type == "edit":
                result = self._edit(action["file"], action.get("content", ""))
            elif action_type == "read":
                result = self._read(action["file"])
            else:
                result = self._run(action["command"])
        except Exception as exc:  # noqa: BLE001
            run_error = str(exc)

        summary = self.last_test_summary
        if action_type in {"edit", "run_command"}:
            self.mutating_steps += 1
            targeted = self._run_targeted_tests(action.get("file", "")) if action_type == "edit" else TestSummary(targeted=True)
            if targeted.total > 0 and self.mutating_steps % self.full_run_interval != 0 and targeted.pass_rate < 1.0:
                summary = targeted
            else:
                summary = self._run_full_tests()

        reward = sparse_reward(summary.pass_rate)
        self.last_test_summary = summary
        done = self.step_count >= self.max_steps or (not summary.targeted and summary.total > 0 and summary.pass_rate >= 1.0)

        info = {
            "step": self.step_count,
            "max_steps": self.max_steps,
            "total_bugs": total_bugs(),
            "target_tests": total_tests(),
            "files_changed": self.files_changed,
            "pass_rate": summary.pass_rate,
            "tests_total": summary.total,
            "tests_failed": summary.failed,
            "targeted_run": summary.targeted,
        }
        if run_error:
            info["error"] = run_error

        observation = {
            "action_result": result,
            "step": self.step_count,
            "reward": reward,
            "test_summary": {
                "total": summary.total,
                "passed": summary.passed,
                "failed": summary.failed,
                "pass_rate": summary.pass_rate,
                "targeted": summary.targeted,
            },
        }

        return {"observation": observation, "reward": reward, "done": done, "info": info}
