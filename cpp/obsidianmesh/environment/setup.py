from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from .reward import sparse_reward, TOTAL_BUGS, TOTAL_TESTS


class ObsidianMeshEnvironment:
    SAFE_COMMANDS = {"cmake", "ctest", "cat", "ls", "grep", "find", "head", "tail", "wc"}

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.max_steps = 320
        self.step_count = 0
        self.mutating_steps = 0
        self.full_run_interval = 5
        self.files_changed: list[str] = []
        self.last_summary = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0, "targeted": False}

    def _safe_path(self, rel: str) -> Path:
        if not rel or ".." in rel or rel.startswith("/"):
            raise ValueError("invalid path")
        target = (self.project_dir / rel).resolve()
        root = self.project_dir.resolve()
        if root not in target.parents and target != root:
            raise ValueError("path escapes workspace")
        return target

    def _is_test_path(self, rel: str) -> bool:
        normalized = rel.replace("\\", "/")
        return normalized.startswith("tests/") or "/tests/" in normalized or normalized.endswith("_test.cpp")

    def _validate_action(self, action: dict[str, str]) -> None:
        action_type = action.get("type", "")
        if action_type not in {"edit", "read", "run_command"}:
            raise ValueError("unknown action type")
        if action_type in {"edit", "read"}:
            rel = action.get("file", "")
            self._safe_path(rel)
            if action_type == "edit" and self._is_test_path(rel):
                raise ValueError("editing test files is not allowed")
        if action_type == "run_command":
            args = shlex.split(action.get("command", ""))
            if not args:
                raise ValueError("empty command")
            if args[0] not in self.SAFE_COMMANDS:
                raise ValueError("command not allowed")

    def _run(self, command: str) -> str:
        args = shlex.split(command)
        proc = subprocess.run(args, cwd=self.project_dir, capture_output=True, text=True, check=False)
        return (proc.stdout or "") + (proc.stderr or "")

    def _parse_ctest(self, output: str, targeted: bool) -> dict[str, Any]:
        total = 0
        failed = 0
        for line in output.splitlines():
            if "Total Tests:" in line:
                try:
                    total = int(line.strip().split(":")[-1].strip())
                except ValueError:
                    total = 0
            if "tests failed out of" in line:
                try:
                    failed = int(line.strip().split()[0])
                except ValueError:
                    failed = 0
        passed = max(total - failed, 0)
        pass_rate = (passed / total) if total > 0 else 0.0
        return {"total": total, "passed": passed, "failed": failed, "pass_rate": pass_rate, "targeted": targeted, "output": output}

    def _run_full_tests(self) -> dict[str, Any]:
        self._run("cmake -B build -DCMAKE_BUILD_TYPE=Debug")
        self._run("cmake --build build --parallel")
        out = self._run("ctest --test-dir build --output-on-failure")
        return self._parse_ctest(out, targeted=False)

    def reset(self) -> dict[str, Any]:
        self.step_count = 0
        self.mutating_steps = 0
        self.files_changed = []
        self.last_summary = self._run_full_tests()
        s = self.last_summary
        return {
            "observation": {"action_result": "", "step": 0, "reward": 0.0, "test_summary": {"total": s["total"], "passed": s["passed"], "failed": s["failed"], "pass_rate": s["pass_rate"], "targeted": s["targeted"]}},
            "reward": 0.0,
            "done": False,
            "info": {"step": 0, "max_steps": self.max_steps, "total_bugs": TOTAL_BUGS, "target_tests": TOTAL_TESTS, "files_changed": [], "pass_rate": s["pass_rate"], "tests_total": s["total"], "tests_failed": s["failed"], "targeted_run": s["targeted"]},
        }

    def step(self, action: dict[str, str]) -> dict[str, Any]:
        self.step_count += 1
        try:
            self._validate_action(action)
        except ValueError as exc:
            return {"observation": {"action_result": "", "step": self.step_count}, "reward": 0.0, "done": self.step_count >= self.max_steps, "info": {"error": str(exc), "step": self.step_count}}

        action_type = action["type"]
        result = ""
        run_error = None
        try:
            if action_type == "edit":
                target = self._safe_path(action["file"])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(action.get("content", ""))
                self.files_changed.append(action["file"])
                result = "edit applied"
            elif action_type == "read":
                result = self._safe_path(action["file"]).read_text()
            else:
                result = self._run(action["command"])
        except Exception as exc:  # noqa: BLE001
            run_error = str(exc)

        summary = self.last_summary
        if action_type in {"edit", "run_command"}:
            self.mutating_steps += 1
            summary = self._run_full_tests()

        reward = sparse_reward(summary["pass_rate"])
        self.last_summary = summary
        done = self.step_count >= self.max_steps or (not summary["targeted"] and summary["total"] > 0 and summary["pass_rate"] >= 1.0)
        info = {
            "step": self.step_count,
            "max_steps": self.max_steps,
            "total_bugs": TOTAL_BUGS,
            "target_tests": TOTAL_TESTS,
            "files_changed": self.files_changed,
            "pass_rate": summary["pass_rate"],
            "tests_total": summary["total"],
            "tests_failed": summary["failed"],
            "targeted_run": summary["targeted"],
        }
        if run_error:
            info["error"] = run_error

        return {
            "observation": {"action_result": result, "step": self.step_count, "reward": reward, "test_summary": {"total": summary["total"], "passed": summary["passed"], "failed": summary["failed"], "pass_rate": summary["pass_rate"], "targeted": summary["targeted"]}},
            "reward": reward,
            "done": done,
            "info": info,
        }
