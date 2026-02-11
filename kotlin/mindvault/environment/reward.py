"""
MindVault Reward Function
Principal difficulty: 75 bugs, 510+ tests
Very sparse reward with regression penalties

Kotlin 1.9, Ktor 2.3, Exposed ORM, 10 Microservices
Kafka, PostgreSQL, Redis, Consul
"""
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET

@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    passed: bool
    duration: float = 0.0
    category: str = "unit"
    bug_markers: List[str] = field(default_factory=list)
    error_message: str = ""
    service: str = ""

@dataclass
class RewardBreakdown:
    """Detailed breakdown of reward components."""
    test_pass_score: float
    completion_bonus: float
    bug_bonus: float
    efficiency_bonus: float
    total: float
    details: Dict

# ==============================================================================
# Service to bug mapping (11 modules)
# ==============================================================================
SERVICE_BUG_MAP = {
    "shared": [],
    "gateway": [],
    "auth": [],
    "documents": [],
    "search": [],
    "graph": [],
    "embeddings": [],
    "collab": [],
    "billing": [],
    "notifications": [],
    "analytics": [],
}

# ==============================================================================
# Reward thresholds and values (Principal - 8 thresholds, very sparse)
# ==============================================================================
REWARD_THRESHOLDS = [0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARD_VALUES = [0.0, 0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
CATEGORY_BONUS = 0.01
SERVICE_BONUS = 0.01
REGRESSION_PENALTY = -0.03

# ==============================================================================
# Test category weights
# ==============================================================================
CATEGORY_WEIGHTS = {
    "unit": 1.0,
    "integration": 1.5,
    "coroutine": 2.5,
    "security": 2.0,
}

class RewardCalculator:
    """
    Calculate reward for the MindVault debugging environment.

    Principal difficulty with 8 sparse thresholds:
    - Bug fix rate mapped to stepped reward values
    - Category completion bonus: +0.01 per fully fixed category (12 categories)
    - Service isolation bonus: +0.01 per fully passing service (11 modules)
    - Regression penalty: -0.03 per regressed test
    - Coroutine and security fix bonuses
    """

    def __init__(self, max_steps: int = 200):
        self.max_steps = max_steps

    def calculate(
        self,
        test_results: List[TestResult],
        step_count: int,
        previous_results: Optional[List[TestResult]] = None,
    ) -> RewardBreakdown:
        """
        Calculate total reward from test results.

        Args:
            test_results: List of test results from Gradle/JUnit run
            step_count: Current step/action count
            previous_results: Previous test results for regression detection

        Returns:
            RewardBreakdown with detailed scoring
        """
        test_pass_score = self._calculate_sparse_pass_rate(test_results)
        completion_bonus = self._calculate_strict_completion_bonus(test_results)
        bug_bonus = 0.0
        efficiency_bonus = self._calculate_efficiency_bonus(test_results, step_count)

        regression_penalty = 0.0
        if previous_results:
            regression_penalty = self._calculate_regression_penalty(
                test_results, previous_results
            )

        # Coroutine bonus
        coroutine_bonus = 0.0
        failing = {r.name for r in test_results if not r.passed}
        coroutine_keywords = [
            "runblocking", "globalscope", "flow", "channel", "dispatcher",
            "async", "coroutine", "mutex", "supervisor", "unconfined",
        ]
        if not any(
            any(kw in t.lower() for kw in coroutine_keywords) for t in failing
        ):
            coroutine_bonus = 0.03

        # Security bonus
        security_bonus = 0.0
        security_keywords = [
            "injection", "traversal", "ssrf", "jwt_none", "timing",
            "deserialization", "xxe", "api_key",
        ]
        if not any(
            any(kw in t.lower() for kw in security_keywords) for t in failing
        ):
            security_bonus = 0.02

        total = (
            test_pass_score * 0.40
            + completion_bonus * 0.25
            + bug_bonus * 0.25
            + efficiency_bonus * 0.05
            + coroutine_bonus
            + security_bonus
            - regression_penalty * 0.15
        )
        total = max(0.0, min(total, 1.0))

        return RewardBreakdown(
            test_pass_score=test_pass_score,
            completion_bonus=completion_bonus,
            bug_bonus=bug_bonus,
            efficiency_bonus=efficiency_bonus,
            total=total,
            details=self._get_details(test_results, step_count, regression_penalty),
        )

    def _calculate_sparse_pass_rate(self, results: List[TestResult]) -> float:
        """
        Calculate sparse pass rate using test pass ratio and 8-threshold mapping.

        Uses REWARD_THRESHOLDS and REWARD_VALUES for stepped rewards.
        """
        if not results:
            return 0.0

        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        pass_rate = passed_count / total_count if total_count > 0 else 0.0

        reward = 0.0
        for i, threshold in enumerate(REWARD_THRESHOLDS):
            if pass_rate >= threshold:
                reward = REWARD_VALUES[i]

        return reward

    def _calculate_strict_completion_bonus(self, results: List[TestResult]) -> float:
        """
        Calculate strict completion bonus.

        Only counts categories where ALL tests pass.
        """
        category_stats = {}
        for result in results:
            cat = result.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0}
            category_stats[cat]["total"] += 1
            if result.passed:
                category_stats[cat]["passed"] += 1

        categories_complete = sum(
            1 for stats in category_stats.values()
            if stats["total"] > 0 and stats["passed"] == stats["total"]
        )

        bonus = categories_complete * CATEGORY_BONUS
        return min(bonus, 1.0)

    def _calculate_regression_penalty(
        self,
        current: List[TestResult],
        previous: List[TestResult],
    ) -> float:
        """
        Calculate penalty for regressions (tests that were passing now fail).

        Penalty: -0.03 per test that was passing but now fails.
        """
        prev_status = {r.name: r.passed for r in previous}
        curr_status = {r.name: r.passed for r in current}

        regressions = sum(
            1
            for name, was_passing in prev_status.items()
            if was_passing and not curr_status.get(name, False)
        )

        if not previous:
            return 0.0

        return min(regressions * abs(REGRESSION_PENALTY), 1.0)

    def _calculate_efficiency_bonus(
        self,
        results: List[TestResult],
        step_count: int,
    ) -> float:
        """
        Calculate progressive efficiency bonus.

        Rewards high pass rate achieved with remaining step budget.
        """
        if not results:
            return 0.0

        pass_rate = sum(1 for r in results if r.passed) / len(results)
        remaining_budget = max(0.0, 1.0 - step_count / self.max_steps)
        return pass_rate * remaining_budget

    def _get_details(
        self,
        results: List[TestResult],
        step_count: int,
        regression_penalty: float = 0.0,
    ) -> Dict:
        """Get detailed breakdown of results."""
        category_breakdown = {}
        for result in results:
            cat = result.category
            if cat not in category_breakdown:
                category_breakdown[cat] = {"total": 0, "passed": 0, "failed": []}
            category_breakdown[cat]["total"] += 1
            if result.passed:
                category_breakdown[cat]["passed"] += 1
            else:
                category_breakdown[cat]["failed"].append(result.name)

        for cat in category_breakdown:
            stats = category_breakdown[cat]
            stats["pass_rate"] = (
                stats["passed"] / stats["total"] if stats["total"] > 0 else 0
            )

        return {
            "total_tests": len(results),
            "passed_tests": sum(1 for r in results if r.passed),
            "failed_tests": sum(1 for r in results if not r.passed),
            "pass_rate": (
                sum(1 for r in results if r.passed) / len(results) if results else 0
            ),
            "step_count": step_count,
            "max_steps": self.max_steps,
            "regression_penalty": regression_penalty,
            "category_breakdown": category_breakdown,
        }

    def get_dependency_stats(self) -> Dict[str, Any]:
        """Get statistics about bug dependency graph."""
        return {
            "bugs_with_dependencies": 0,
            "dependency_percentage": 0,
            "max_chain_depth": 0,
            "diamond_patterns": 0,
            "cross_category_links": 0,
        }

def parse_junit_reports(results_dir: Path) -> List[TestResult]:
    """
    Parse JUnit XML test reports from a single module directory.

    Args:
        results_dir: Path to build/test-results/test directory

    Returns:
        List of TestResult objects
    """
    results = []
    seen = set()

    if not results_dir.exists():
        return results

    def categorize(classname: str) -> str:
        if ".coroutine." in classname:
            return "coroutine"
        elif ".security." in classname:
            return "security"
        elif ".integration." in classname:
            return "integration"
        return "unit"

    for xml_file in results_dir.glob("TEST-*.xml"):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            for testcase in root.findall("testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_val = float(testcase.get("time", "0"))

                if name in seen:
                    continue

                skipped = testcase.find("skipped")
                if skipped is not None:
                    continue

                seen.add(name)

                failure = testcase.find("failure")
                error = testcase.find("error")
                passed = failure is None and error is None

                category = categorize(classname)

                # Determine service from classname
                service = "shared"
                for svc in SERVICE_BUG_MAP:
                    if f".{svc}." in classname.lower():
                        service = svc
                        break

                error_msg = ""
                if not passed:
                    fail_elem = failure if failure is not None else error
                    if fail_elem is not None and fail_elem.text:
                        error_msg = fail_elem.text[:500]

                results.append(
                    TestResult(
                        name=name,
                        passed=passed,
                        duration=time_val,
                        category=category,
                        bug_markers=[],
                        error_message=error_msg,
                        service=service,
                    )
                )
        except ET.ParseError:
            continue

    return results

def parse_junit_reports_recursive(project_dir: Path) -> List[TestResult]:
    """
    Parse JUnit XML test reports recursively through all module build directories.

    Searches for TEST-*.xml files in any path matching:
        */build/test-results/test/TEST-*.xml

    Args:
        project_dir: Root project directory containing all modules

    Returns:
        Combined list of TestResult objects from all modules
    """
    results = []
    seen = set()

    def categorize(classname: str) -> str:
        if ".coroutine." in classname:
            return "coroutine"
        elif ".security." in classname:
            return "security"
        elif ".integration." in classname:
            return "integration"
        return "unit"

    # Search recursively for JUnit XML files in all module build dirs
    for xml_file in project_dir.rglob("build/test-results/test/TEST-*.xml"):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Determine which module this report belongs to
            rel_path = xml_file.relative_to(project_dir)
            module_name = str(rel_path.parts[0]) if len(rel_path.parts) > 1 else "shared"

            for testcase in root.findall("testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_val = float(testcase.get("time", "0"))

                if name in seen:
                    continue

                skipped = testcase.find("skipped")
                if skipped is not None:
                    continue

                seen.add(name)

                failure = testcase.find("failure")
                error = testcase.find("error")
                passed = failure is None and error is None

                category = categorize(classname)

                # Determine service from classname or module path
                service = module_name
                for svc in SERVICE_BUG_MAP:
                    if f".{svc}." in classname.lower():
                        service = svc
                        break

                error_msg = ""
                if not passed:
                    fail_elem = failure if failure is not None else error
                    if fail_elem is not None and fail_elem.text:
                        error_msg = fail_elem.text[:500]

                results.append(
                    TestResult(
                        name=name,
                        passed=passed,
                        duration=time_val,
                        category=category,
                        bug_markers=[],
                        error_message=error_msg,
                        service=service,
                    )
                )
        except ET.ParseError:
            continue

    return results

def calculate_reward(current_results, initial_results):
    """
    Simplified reward calculation matching EventHorizon pattern.

    Args:
        current_results: List of TestResult from current test run
        initial_results: List of TestResult from initial baseline run

    Returns:
        Dict with reward breakdown
    """
    if not current_results:
        return {
            "reward": 0.0,
            "tests_passed": 0,
            "tests_total": 0,
            "pass_rate": 0.0,
            "bugs_fixed": 0,
            "bugs_total": 0,
            "categories_complete": 0,
            "services_complete": 0,
            "regressions": 0,
        }

    current_passed = {r.name for r in current_results if r.passed}
    initial_passed = {r.name for r in initial_results if r.passed}

    passed_count = len(current_passed)
    total_count = len(current_results)
    pass_rate = passed_count / total_count if total_count > 0 else 0.0

    reward = 0.0
    for i, threshold in enumerate(REWARD_THRESHOLDS):
        if pass_rate >= threshold:
            reward = REWARD_VALUES[i]

    # Count category completions
    category_stats = {}
    for r in current_results:
        cat = r.category
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1
        if r.passed:
            category_stats[cat]["passed"] += 1

    categories_complete = sum(
        1 for stats in category_stats.values()
        if stats["total"] > 0 and stats["passed"] == stats["total"]
    )
    reward += categories_complete * CATEGORY_BONUS

    regressions = sum(1 for t in initial_passed if t not in current_passed)
    reward += regressions * REGRESSION_PENALTY
    reward = max(0.0, min(1.0, reward))

    return {
        "reward": round(reward, 4),
        "tests_passed": len(current_passed),
        "tests_total": len(current_results),
        "pass_rate": round(pass_rate, 4),
        "bugs_fixed": 0,
        "bugs_total": 0,
        "categories_complete": categories_complete,
        "services_complete": 0,
        "regressions": regressions,
    }

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
BUG_CATEGORIES = {}
