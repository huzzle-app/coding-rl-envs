"""
MindVault Reward Function
Principal difficulty: 80 bugs, 536 tests
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
    "shared": [
        "L1", "L2", "L3", "L4", "L5",
        "C7", "C8", "F7", "G4", "G5",
        "H4", "H5", "I7", "I8", "J2", "J4",
        "K7", "K8", "E8", "A9", "A10",
        "B6", "D5", "E7", "J3", "J5", "K2",
    ],
    "gateway": ["A1", "A2", "D1", "D2", "I1", "I2", "I3"],
    "auth": ["D3", "G1", "I4", "I5"],
    "documents": ["A3", "A4", "B1", "C1", "C2", "E1", "E2", "F1", "I6"],
    "search": ["A5", "B2", "C3", "E3", "F2", "H1", "H2", "K1"],
    "graph": ["A6", "B3", "C4", "C5", "E4", "F3", "F4", "H3"],
    "embeddings": ["A7", "B4", "F5", "K3"],
    "collab": ["A8", "D4", "G2", "K4"],
    "billing": ["B5", "C6", "E5", "E6", "K5"],
    "notifications": ["F6", "K6"],
    "analytics": ["G3", "J1"],
}

# ==============================================================================
# Reward thresholds and values (Principal - 8 thresholds, very sparse)
# ==============================================================================
REWARD_THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARD_VALUES = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
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

# Bug categories (12 categories, 80 bugs)
BUG_CATEGORIES = {
    "A": {"name": "Coroutines & Structured Concurrency", "bugs": ["A1","A2","A3","A4","A5","A6","A7","A8","A9","A10"]},
    "B": {"name": "Platform Types & Null Safety", "bugs": ["B1","B2","B3","B4","B5","B6"]},
    "C": {"name": "Data Classes & Enums", "bugs": ["C1","C2","C3","C4","C5","C6","C7","C8"]},
    "D": {"name": "Error Handling", "bugs": ["D1","D2","D3","D4","D5"]},
    "E": {"name": "Database & Exposed ORM", "bugs": ["E1","E2","E3","E4","E5","E6","E7","E8"]},
    "F": {"name": "Serialization", "bugs": ["F1","F2","F3","F4","F5","F6","F7"]},
    "G": {"name": "Objects & Delegation", "bugs": ["G1","G2","G3","G4","G5"]},
    "H": {"name": "Caching", "bugs": ["H1","H2","H3","H4","H5"]},
    "I": {"name": "Security", "bugs": ["I1","I2","I3","I4","I5","I6","I7","I8"]},
    "J": {"name": "Observability", "bugs": ["J1","J2","J3","J4","J5"]},
    "K": {"name": "Kotlin Idioms", "bugs": ["K1","K2","K3","K4","K5","K6","K7","K8"]},
    "L": {"name": "Setup & Infrastructure", "bugs": ["L1","L2","L3","L4","L5"]},
}

# Bug dependency graph
BUG_DEPENDENCIES = {
    "L1": [],
    "L2": ["L1"],
    "L3": ["L1"],
    "L4": ["L1"],
    "L5": ["L1"],
    "A1": ["L1", "L2"],
    "A2": ["A1"],
    "A3": ["L1", "L2"],
    "A4": ["A3"],
    "A5": ["L1", "L2"],
    "A6": ["L1", "L2"],
    "A7": ["L1", "L2"],
    "A8": ["L1", "L2"],
    "A9": ["L1", "L2"],
    "A10": ["A9"],
    "D1": ["A1"],
    "D2": ["D1"],
    "I1": ["L1", "L2"],
    "I2": ["I1"],
    "I3": ["I1", "I2"],
    "I4": ["L1", "L2"],
    "I5": ["I4"],
    "F1": ["L1", "L2"],
    "F2": ["F1"],
    "F3": ["F1"],
    "F4": ["F3"],
    "F5": ["F1"],
    "F6": ["F1"],
    "F7": ["F1"],
    "E1": ["L1", "L2"],
    "E2": ["E1"],
    "E3": ["E1"],
    "E4": ["E1"],
    "E5": ["E1"],
    "E6": ["E5"],
}

# Bug to test mapping (maps bug IDs to test method names that verify the fix)
BUG_TEST_MAPPING = {
    "A1": ["test_no_run_blocking_in_handler"],
    "A2": ["test_no_global_scope"],
    "A3": ["test_flow_cancellation_respected"],
    "A4": ["test_structured_scope_used"],
    "A5": ["test_produce_channel_consumed", "test_no_producer_leak"],
    "A6": ["test_lock_scope_within_dispatcher"],
    "A7": ["test_await_all_partial_failure", "test_supervisor_scope_independent"],
    "A8": ["test_late_subscriber_receives"],
    "A9": ["test_callback_flow_await_close", "test_flow_completes_properly"],
    "A10": ["test_thread_safe_state_access"],
    "B1": ["test_jdbc_result_null_safe"],
    "B2": ["test_platform_type_cast_safe"],
    "B3": ["test_null_let_returns_null"],
    "B4": ["test_meaningful_init_error", "test_lateinit_initialized"],
    "B5": ["test_bigdecimal_null_check", "test_no_balance_returns_zero"],
    "B6": ["test_map_cast_safe", "test_nested_json_typed"],
    "C1": ["test_bytearray_content_equals"],
    "C2": ["test_metadata_copy_deep", "test_original_tags_unchanged"],
    "C3": ["test_discriminator_no_collision", "test_type_field_distinct"],
    "C4": ["test_edge_type_serialization"],
    "C5": ["test_value_class_map_key"],
    "C6": ["test_invoice_copy_recalculates"],
    "C7": ["test_object_state_isolated", "test_no_singleton_leak"],
    "C8": ["test_enum_serial_name_correct", "test_wire_format_matches"],
    "D1": ["test_status_pages_rethrows_cancel", "test_cancellation_not_caught"],
    "D2": ["test_single_respond_per_call", "test_no_double_respond"],
    "D3": ["test_expired_token_returns_401"],
    "D4": ["test_websocket_close_handled", "test_disconnect_no_exception"],
    "D5": ["test_error_handler_preserves_type", "test_error_handler_not_generic_catch"],
    "E1": ["test_suspended_transaction_used"],
    "E2": ["test_schema_create_in_transaction", "test_init_tables_wrapped"],
    "E3": ["test_op_build_precedence", "test_query_correct_parentheses"],
    "E4": ["test_entity_cache_cleared", "test_fresh_data_after_dsl_update"],
    "E5": ["test_large_batch_no_oom", "test_batch_insert_no_returning"],
    "E6": ["test_isolation_level_correct", "test_lock_held_in_transaction"],
    "E7": ["test_varchar_length_validated", "test_no_silent_truncation"],
    "E8": ["test_pool_size_sufficient", "test_concurrent_transactions_succeed"],
    "F1": ["test_instant_serializer_registered"],
    "F2": ["test_discriminator_no_collision"],
    "F3": ["test_ignore_unknown_keys", "test_extra_fields_tolerated"],
    "F4": ["test_field_not_serialized", "test_kotlinx_transient_used"],
    "F5": ["test_mixed_type_serialization"],
    "F6": ["test_enum_case_insensitive", "test_lowercase_enum_deserialized"],
    "F7": ["test_json_element_used", "test_no_map_string_any"],
    "G1": ["test_delegation_not_recreated", "test_cache_singleton_instance"],
    "G2": ["test_lazy_thread_safe_mode"],
    "G3": ["test_companion_logger_class", "test_log_correct_class_name"],
    "G4": ["test_companion_serializer_stateless"],
    "G5": ["test_delegation_correct_receiver", "test_interface_delegation_this"],
    "H1": ["test_cache_key_stable", "test_no_timestamp_in_key"],
    "H2": ["test_cache_stampede_prevented", "test_single_flight_pattern"],
    "H3": ["test_cache_schema_evolution", "test_old_cache_deserializes"],
    "H4": ["test_cache_bounded_size", "test_no_unbounded_growth"],
    "H5": ["test_kotlin_duration_used"],
    "I1": ["test_sql_injection_prevented", "test_exposed_dsl_parameterized"],
    "I2": ["test_path_traversal_blocked", "test_canonical_path_checked"],
    "I3": ["test_ssrf_internal_blocked"],
    "I4": ["test_jwt_none_rejected", "test_algorithm_enforced"],
    "I5": ["test_no_timing_leak", "test_constant_time_comparison"],
    "I6": ["test_safe_deserialization"],
    "I7": ["test_xxe_disabled", "test_external_entities_blocked"],
    "I8": ["test_api_key_constant_time"],
    "J1": ["test_mdc_propagated_in_coroutine", "test_trace_id_preserved"],
    "J2": ["test_exception_handler_error_level", "test_errors_visible"],
    "J3": ["test_kafka_trace_header_extracted", "test_distributed_trace_continues"],
    "J4": ["test_run_catching_rethrows_cancel", "test_cancellation_not_swallowed"],
    "J5": ["test_call_logging_before_status", "test_error_responses_logged"],
    "K1": ["test_dsl_scope_restricted", "test_no_outer_scope_access"],
    "K2": ["test_sequence_terminal_operation", "test_no_eager_collection_in_pipeline"],
    "K3": ["test_retry_iterative", "test_no_stack_overflow_on_retry"],
    "K4": ["test_operator_commutative", "test_merge_order_independent"],
    "K5": ["test_bigdecimal_rounding_explicit", "test_extension_correct_scale"],
    "K6": ["test_build_list_immutable", "test_list_not_cast_to_mutable"],
    "K7": ["test_suspend_lambda_wrapper", "test_sam_conversion_correct"],
    "K8": ["test_value_class_jvm_inline", "test_no_boxing_on_boundary"],
    "L1": ["test_gradle_root_plugin_config", "test_subprojects_build"],
    "L2": ["test_hocon_optional_substitution", "test_missing_env_var_fallback"],
    "L3": ["test_http_client_shared", "test_no_client_per_request"],
    "L4": ["test_consul_lazy_init", "test_consul_retry_on_startup"],
    "L5": ["test_settings_module_paths", "test_all_modules_resolved"],
}
