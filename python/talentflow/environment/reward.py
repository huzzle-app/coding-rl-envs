"""
TalentFlow Reward Function

Calculates reward based on test results and bug detection.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import re

@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    passed: bool
    duration: float
    category: str  # unit, integration, system, security
    bug_markers: List[str]  # e.g., ['bug_a1', 'bug_c2']

@dataclass
class RewardBreakdown:
    """Detailed breakdown of reward components."""
    test_pass_score: float
    completion_bonus: float
    bug_bonus: float
    efficiency_bonus: float
    total: float
    details: Dict

# Test weights by category
CATEGORY_WEIGHTS = {
    'unit': 1.0,
    'integration': 1.5,
    'system': 2.5,
    'security': 2.0,
}

class RewardCalculator:
    """
    Calculate reward for the TalentFlow debugging environment.

    Reward components (harder version):
    1. Sparse test pass rate with thresholds (40%)
    2. Category completion bonus with all-or-nothing (25%)
    3. Bug detection bonus with dependencies (25%)
    4. Efficiency bonus (5%)
    5. Regression penalty (can reduce total)

    The reward is designed to be sparse - no meaningful reward
    until significant progress is made.
    """

    def __init__(self, max_steps: int = 150):
        self.max_steps = max_steps
        # 5-threshold sparse reward for Senior tier (step function, matches scoring.py)
        self.pass_thresholds = [0.50, 0.75, 0.90, 1.0]
        self.threshold_rewards = [0.15, 0.35, 0.65, 1.0]

    def calculate(
        self,
        test_results: List[TestResult],
        step_count: int,
        previous_results: Optional[List[TestResult]] = None
    ) -> RewardBreakdown:
        """
        Calculate total reward from test results.

        Args:
            test_results: List of test results from pytest run
            step_count: Current step/action count
            previous_results: Previous test results for delta calculation

        Returns:
            RewardBreakdown with detailed scoring
        """
        test_pass_score = self._calculate_sparse_pass_rate(test_results)

        completion_bonus = self._calculate_strict_completion_bonus(test_results)

        bug_bonus = self._calculate_bug_bonus_with_dependencies(test_results)

        efficiency_bonus = self._calculate_efficiency_bonus(
            test_results, step_count
        )

        regression_penalty = 0.0
        if previous_results:
            regression_penalty = self._calculate_regression_penalty(
                test_results, previous_results
            )

        total = (
            test_pass_score * 0.40 +
            completion_bonus * 0.25 +
            bug_bonus * 0.25 +
            efficiency_bonus * 0.05 -
            regression_penalty * 0.15
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
        Calculate sparse pass rate with thresholds (step function).

        No reward until 50% pass rate, then step increases.
        """
        if not results:
            return 0.0

        total_weight = 0.0
        weighted_passes = 0.0

        for result in results:
            weight = CATEGORY_WEIGHTS.get(result.category, 1.0)
            total_weight += weight
            if result.passed:
                weighted_passes += weight

        pass_rate = weighted_passes / total_weight if total_weight > 0 else 0.0

        # Step function: find highest threshold that pass_rate meets
        for threshold, reward in reversed(list(zip(self.pass_thresholds, self.threshold_rewards))):
            if pass_rate >= threshold:
                return reward
        return 0.0

    def _calculate_strict_completion_bonus(self, results: List[TestResult]) -> float:
        """
        Calculate strict completion bonus.

        Only counts categories where ALL tests pass.
        Bonus requires at least 2 categories complete.
        """
        category_stats = {}

        for result in results:
            cat = result.category
            if cat not in category_stats:
                category_stats[cat] = {'total': 0, 'passed': 0}
            category_stats[cat]['total'] += 1
            if result.passed:
                category_stats[cat]['passed'] += 1

        complete_categories = 0
        for cat, stats in category_stats.items():
            if stats['total'] > 0 and stats['passed'] == stats['total']:
                complete_categories += 1

        if complete_categories < 2:
            return 0.0

        return min((complete_categories - 1) * 0.25, 1.0)

    def _calculate_bug_bonus_with_dependencies(self, results: List[TestResult]) -> float:
        """
        Calculate bug bonus considering dependencies.

        A bug only counts toward bonus if its prerequisites are also fixed.
        """
        if not BUG_TEST_MAPPING:
            return 0.0

        # Build test name -> pass/fail map
        test_status = {r.name: r.passed for r in results}

        # Determine which bugs are fixed
        fixed_bugs = set()
        for bug_id, test_names in BUG_TEST_MAPPING.items():
            matching = [name for name in test_names if name in test_status]
            if matching and all(test_status.get(name, False) for name in matching):
                fixed_bugs.add(bug_id)

        # Only count bugs whose dependencies are also fixed
        valid_fixes = set()
        for bug_id in fixed_bugs:
            deps = BUG_DEPENDENCIES.get(bug_id, [])
            if all(d in fixed_bugs for d in deps):
                valid_fixes.add(bug_id)

        total_bugs = len(BUG_TEST_MAPPING)
        if total_bugs == 0:
            return 0.0

        return len(valid_fixes) / total_bugs

    def _calculate_regression_penalty(
        self,
        current: List[TestResult],
        previous: List[TestResult]
    ) -> float:
        """
        Calculate penalty for regressions (tests that were passing now fail).
        """
        prev_status = {r.name: r.passed for r in previous}
        curr_status = {r.name: r.passed for r in current}

        regressions = 0
        for name, was_passing in prev_status.items():
            if was_passing and not curr_status.get(name, False):
                regressions += 1

        if not previous:
            return 0.0

        return min(regressions / len(previous), 1.0)

    def _calculate_efficiency_bonus(
        self,
        results: List[TestResult],
        step_count: int
    ) -> float:
        """
        Calculate progressive efficiency bonus.

        Rewards high pass rate achieved with remaining step budget.
        Formula: pass_rate * (1.0 - step_count / max_steps)
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
        regression_penalty: float = 0.0
    ) -> Dict:
        """Get detailed breakdown of results."""
        category_breakdown = {}
        for result in results:
            cat = result.category
            if cat not in category_breakdown:
                category_breakdown[cat] = {'total': 0, 'passed': 0, 'failed': []}
            category_breakdown[cat]['total'] += 1
            if result.passed:
                category_breakdown[cat]['passed'] += 1
            else:
                category_breakdown[cat]['failed'].append(result.name)

        for cat in category_breakdown:
            stats = category_breakdown[cat]
            stats['pass_rate'] = stats['passed'] / stats['total'] if stats['total'] > 0 else 0

        return {
            'total_tests': len(results),
            'passed_tests': sum(1 for r in results if r.passed),
            'failed_tests': sum(1 for r in results if not r.passed),
            'pass_rate': sum(1 for r in results if r.passed) / len(results) if results else 0,
            'step_count': step_count,
            'max_steps': self.max_steps,
            'regression_penalty': regression_penalty,
            'category_breakdown': category_breakdown,
        }

def calculate_reward(
    test_results: List[Dict],
    step_count: int,
    max_steps: int = 100
) -> float:
    """
    Simplified reward calculation function.

    Args:
        test_results: List of dicts with 'name', 'passed', 'category' keys
        step_count: Current step count
        max_steps: Maximum steps allowed

    Returns:
        Float reward between 0.0 and 1.0
    """
    results = [
        TestResult(
            name=r['name'],
            passed=r['passed'],
            duration=r.get('duration', 0.0),
            category=r.get('category', 'unit'),
            bug_markers=r.get('markers', []),
        )
        for r in test_results
    ]

    calculator = RewardCalculator(max_steps=max_steps)
    breakdown = calculator.calculate(results, step_count)

    return breakdown.total

def parse_pytest_output(output: str) -> List[TestResult]:
    """
    Parse pytest output to extract test results.

    Args:
        output: Raw pytest output string

    Returns:
        List of TestResult objects
    """
    results = []
    seen_tests = set()

    def _categorize(file_path: str) -> str:
        if 'unit/' in file_path:
            return 'unit'
        elif 'integration/' in file_path:
            return 'integration'
        elif 'system/' in file_path:
            return 'system'
        elif 'security/' in file_path:
            return 'security'
        return 'unit'

    def _add_result(test_name: str, nodeid: str, file_path: str, status: str):
        if nodeid in seen_tests:
            return
        seen_tests.add(nodeid)

        category = _categorize(file_path)

        results.append(TestResult(
            name=test_name,
            passed=status == 'PASSED',
            duration=0.0,
            category=category,
            bug_markers=[],
        ))

    # Pattern for class-based tests: file::Class::test_name[params] STATUS
    class_pattern = r'(tests/\S+)::(\w+)::(test_\w+(?:\[[\S]*\])?)\s+(PASSED|FAILED|ERROR|SKIPPED)'
    for match in re.finditer(class_pattern, output):
        file_path, class_name, test_name, status = match.groups()
        nodeid = f'{file_path}::{class_name}::{test_name}'
        bare_name = re.sub(r'\[.*\]$', '', test_name)
        _add_result(bare_name, nodeid, file_path, status)

    # Pattern for function-level tests: file::test_name[params] STATUS
    func_pattern = r'(tests/\S+)::(test_\w+(?:\[[\S]*\])?)\s+(PASSED|FAILED|ERROR|SKIPPED)'
    for match in re.finditer(func_pattern, output):
        file_path, test_name, status = match.groups()
        nodeid = f'{file_path}::{test_name}'
        bare_name = re.sub(r'\[.*\]$', '', test_name)
        _add_result(bare_name, nodeid, file_path, status)

    return results

# Bug-to-test mapping for RL training reward tracking
BUG_TEST_MAPPING = {
    'a1': ['test_connection_health_check', 'test_connection_max_age_configuration', 'test_parallel_queries_connection_exhaustion', 'test_connection_reuse'],
    'a2': ['test_prefetch_skills_correctly', 'test_n_plus_one_with_wrong_prefetch', 'test_status_field_should_have_index', 'test_candidate_list_query_count'],
    'a3': ['test_concurrent_job_applications', 'test_safe_concurrent_applications', 'test_application_race_condition_prevention', 'test_concurrent_application_limit_check', 'test_duplicate_application_prevention'],
    'b1': ['test_celery_timezone_matches_django', 'test_celery_timezone_setting', 'test_scheduled_task_time', 'test_webhook_timing_accuracy'],
    'b2': ['test_chord_callback_pattern', 'test_chord_with_ignore_result_fails', 'test_chord_result_collection', 'test_webhook_batch_delivery'],
    'b3': ['test_cache_error_doesnt_release_connection', 'test_connection_accumulation_on_repeated_operations', 'test_connections_grow_without_bound', 'test_query_cache_no_cleanup', 'test_webhook_retry_mechanism'],
    'c1': ['test_concurrent_refresh_race_condition', 'test_token_replay_prevention', 'test_revoked_token_reuse_detection', 'test_concurrent_token_refresh', 'test_token_reuse_detection'],
    'c2': ['test_oauth_state_csrf_attack_scenario', 'test_oauth_callback_without_state_is_vulnerable', 'test_oauth_callback_without_state_rejected', 'test_oauth_callback_with_invalid_state_rejected', 'test_oauth_state_must_be_validated', 'test_oauth_state_required', 'test_oauth_state_single_use'],
    'd1': ['test_settings_import_order'],
    'd2': ['test_no_conflicting_packages', 'test_psycopg2_single_version'],
    'e1': ['test_perfect_skill_match_score', 'test_perfect_match_equals_one', 'test_skill_match_with_no_requirements'],
    'e2': ['test_slot_availability_timezone', 'test_realtime_dashboard_uses_naive_datetime', 'test_interview_scheduling_timezone_awareness', 'test_interview_slot_timezone_handling'],
    'f1': ['test_score_update_counter_increment', 'test_concurrent_score_updates', 'test_counter_race_condition'],
    'f2': ['test_score_with_seven_years_experience', 'test_score_with_eight_skills', 'test_score_consistency_across_values', 'test_report_data_integrity_check'],
    'f3': ['test_connection_accumulation', 'test_batch_cache_creates_many_connections'],
    'f4': ['test_permission_check_logic', 'test_role_hierarchy_enforcement', 'test_company_access_verification', 'test_token_action_validation', 'test_impersonation_requires_admin'],
    'g1': ['test_report_timezone_consistency'],
    'g2': ['test_strftime_locale_dependency', 'test_export_format_consistency'],
    'g3': ['test_unicode_candidate_creation_preserved', 'test_unicode_in_notes_preserved', 'test_unicode_name_preservation', 'test_notification_with_unicode_name', 'test_bulk_import_data_normalization'],
    'g4': ['test_weighted_score_basic', 'test_weighted_score_different_weights', 'test_scores_equal_comparison', 'test_score_delta_calculation', 'test_aggregate_perfect_matches', 'test_normalize_scores', 'test_percentile_rank_calculation'],
    'h1': ['test_comprehensive_report_deadlock_potential', 'test_lock_order_company_job_candidate', 'test_lock_order_candidate_job'],
    'h2': ['test_concurrent_deduplication'],
    'h3': ['test_report_data_consistency', 'test_count_vs_locked_mismatch', 'test_report_caching_efficiency', 'test_generate_and_cache_report'],
    'i1': ['test_advanced_search_order_by_injection', 'test_order_by_with_union_injection', 'test_order_by_with_subquery_injection', 'test_order_by_time_based_injection', 'test_search_query_sanitization', 'test_sql_characters_sanitized'],
    'i2': ['test_sync_external_candidates_ssrf', 'test_ssrf_with_file_protocol', 'test_ssrf_url_construction', 'test_external_sync_url_validation'],
    's5': ['test_circular_import_resolved', 'test_candidates_utils_importable'],
    's6': ['test_helpers_init_exists', 'test_validators_importable'],
    's7': ['test_migration_chain_valid', 'test_migration_dependencies_correct'],
    's8': ['test_debug_env_var_coercion', 'test_debug_false_string_is_false'],
    's9': ['test_no_conflicting_packages', 'test_psycopg2_single_version'],
    's10': ['test_settings_module_path_correct', 'test_manage_py_settings_path'],
}

# Bug dependency chains (prerequisite bugs that must be fixed first)
BUG_DEPENDENCIES = {
    's5': [],      # No dependencies - fix first
    's6': [],      # No dependencies
    's7': [],      # No dependencies
    's8': [],      # No dependencies
    's9': [],      # No dependencies
    's10': [],     # No dependencies
    'd1': ['s5'],
    'd2': ['s9'],
    'a1': ['s5', 's7'],
    'a2': ['s5', 's7'],
    'a3': ['s5', 's7'],
    'b1': ['s5', 'd1'],
    'b2': ['s5'],
    'b3': ['s5'],
    'c1': ['s5', 's7'],
    'c2': ['s5', 's7'],
    'e1': ['s5'],
    'e2': ['s5', 'b1'],
    'f1': ['s5'],
    'f2': ['s5', 'e1'],
    'f3': ['s5', 'b3'],
    'f4': ['s5', 'c1'],
    'g1': ['s5', 'e2'],
    'g2': ['s5'],
    'g3': ['s5'],
    'g4': ['s5', 'e1'],
    'h1': ['s5', 'a3'],
    'h2': ['s5', 'a3'],
    'h3': ['s5', 'a2'],
    'i1': ['s5'],
    'i2': ['s5'],
}

# Bug categories for setup.py
BUG_CATEGORIES = {
    'setup': ['s5', 's6', 's7', 's8', 's9', 's10'],
    'database': ['a1', 'a2', 'a3'],
    'celery': ['b1', 'b2', 'b3'],
    'auth': ['c1', 'c2'],
    'config': ['d1', 'd2'],
    'logic': ['e1', 'e2'],
    'heisenbug': ['f1', 'f2', 'f3', 'f4'],
    'data': ['g1', 'g2', 'g3', 'g4'],
    'cascading': ['h1', 'h2', 'h3'],
    'security': ['i1', 'i2'],
}


def validate_test_integrity(test_results: List[TestResult]) -> bool:
    """
    Anti-reward-hacking: validate that test names in results
    correspond to actual test functions in the test files.
    Returns True if results appear legitimate.
    """
    known_test_names = set()
    for tests in BUG_TEST_MAPPING.values():
        known_test_names.update(tests)

    result_names = {r.name for r in test_results}
    # If results contain many unknown test names, flag as suspicious
    known_overlap = result_names & known_test_names
    if known_test_names and not known_overlap:
        return False  # No overlap at all is suspicious
    return True
