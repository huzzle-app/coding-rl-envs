"""
CacheForge Reward Function
Terminal Bench v2 - Sparse Reward System for C++ Cache Server

Sparse rewards with 5 thresholds based on pass rate.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re

@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    passed: bool
    duration: float
    category: str  # unit, integration, concurrency, security

@dataclass
class RewardBreakdown:
    """Detailed breakdown of reward components."""
    test_pass_score: float
    total: float
    details: Dict

# ==============================================================================
# Test category weights
# ==============================================================================
CATEGORY_WEIGHTS = {
    'unit': 1.0,
    'integration': 1.5,
    'concurrency': 2.5,
    'security': 2.0,
}

class RewardCalculator:
    """
    Calculate reward for the CacheForge debugging environment.

    Reward based on sparse test pass rate with thresholds.
    """

    def __init__(self, max_steps: int = 100):
        self.max_steps = max_steps
        # 5-threshold sparse reward for Senior tier (step function, matches scoring.py)
        self.pass_thresholds = [0.50, 0.75, 0.90, 1.0]
        self.threshold_rewards = [0.15, 0.35, 0.65, 1.0]

    def calculate(
        self,
        test_results: List[TestResult],
        step_count: int,
        previous_results: Optional[List[TestResult]] = None,
        cwd: Optional[str] = None,
    ) -> RewardBreakdown:
        test_pass_score = self._calculate_sparse_pass_rate(test_results)

        # Blend: 70% test pass rate + 30% code correctness
        code_correctness = 0.0
        try:
            from environment.code_checks import code_correctness_score
            code_correctness = code_correctness_score(cwd) if cwd else 0.0
        except ImportError:
            pass

        blended = 0.70 * test_pass_score + 0.30 * code_correctness
        total = max(0.0, min(blended, 1.0))

        details = self._get_details(test_results, step_count)
        details['code_correctness'] = round(code_correctness, 4)

        return RewardBreakdown(
            test_pass_score=test_pass_score,
            total=total,
            details=details,
        )

    def _calculate_sparse_pass_rate(self, results: List[TestResult]) -> float:
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

    def _get_details(self, results, step_count):
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

        return {
            'total_tests': len(results),
            'passed_tests': sum(1 for r in results if r.passed),
            'failed_tests': sum(1 for r in results if not r.passed),
            'pass_rate': sum(1 for r in results if r.passed) / len(results) if results else 0,
            'step_count': step_count,
            'max_steps': self.max_steps,
            'category_breakdown': category_breakdown,
        }

def parse_ctest_output(output: str) -> List[TestResult]:
    """Parse ctest output to extract test results."""
    results = []
    seen = set()

    def categorize(suite_name, test_name):
        suite_lower = suite_name.lower()
        name_lower = test_name.lower()
        # Categorize primarily by test suite name (from gtest)
        if 'concurrency' in suite_lower or 'deadlock' in suite_lower:
            return 'concurrency'
        elif 'security' in suite_lower:
            return 'security'
        elif 'integration' in suite_lower or 'persistence' in suite_lower or 'replication' in suite_lower:
            return 'integration'
        elif 'sourcecheck' in suite_lower:
            return 'integration'
        elif 'ubdetection' in suite_lower:
            return 'unit'
        # Fallback to test name heuristics
        elif 'concurrent' in name_lower or 'deadlock' in name_lower:
            return 'concurrency'
        elif 'security' in name_lower or 'injection' in name_lower:
            return 'security'
        elif 'integration' in name_lower or 'pipeline' in name_lower:
            return 'integration'
        return 'unit'

    # GTest output: [ OK ] TestSuite.TestName (N ms)
    # or: [ FAILED ] TestSuite.TestName (N ms)
    ok_pattern = r'\[\s+OK\s+\]\s+(\w+)\.(\w+)\s+\((\d+)\s+ms\)'
    fail_pattern = r'\[\s+FAILED\s+\]\s+(\w+)\.(\w+)'

    for match in re.finditer(ok_pattern, output):
        suite, name, duration = match.groups()
        full_name = f"{suite}.{name}"
        if full_name not in seen:
            seen.add(full_name)
            results.append(TestResult(
                name=full_name, passed=True, duration=float(duration),
                category=categorize(suite, name)
            ))

    for match in re.finditer(fail_pattern, output):
        suite, name = match.groups()
        full_name = f"{suite}.{name}"
        if full_name not in seen:
            seen.add(full_name)
            results.append(TestResult(
                name=full_name, passed=False, duration=0.0,
                category=categorize(suite, name)
            ))

    return results

def calculate_reward(test_results, step_count, max_steps=100):
    """Simplified reward calculation."""
    results = [
        TestResult(
            name=r['name'], passed=r['passed'],
            duration=r.get('duration', 0.0),
            category=r.get('category', 'unit'),
        )
        for r in test_results
    ]
    calc = RewardCalculator(max_steps=max_steps)
    return calc.calculate(results, step_count).total

# ==============================================================================
# Bug-to-test mapping (which tests cover each bug)
# ==============================================================================
BUG_TEST_MAPPING = {
    'L1': ['ConfigTest.test_get_config_returns_valid_instance',
           'ConfigTest.test_config_singleton_same_address',
           'ConfigTest.test_config_not_global_variable'],
    'L3': ['ConfigTest.test_config_handles_invalid_port_string',
           'ConfigTest.test_config_handles_empty_port_string'],
    'L4': ['ServerIntegrationTest.test_config_and_connection_both_included',
           'ServerIntegrationTest.test_config_connection_type_availability'],
    'L2': ['SourceCheckTest.test_signal_handler_no_spdlog',
           'SourceCheckTest.test_signal_handler_uses_sig_atomic_t'],
    'A1': ['SourceCheckTest.test_connection_count_is_synchronized',
           'SourceCheckTest.test_broadcast_is_synchronized'],
    'A2': ['DeadlockTest.test_lock_ordering_set_remove',
           'DeadlockTest.test_lock_ordering_three_threads'],
    'A3': ['ConcurrencyTest.test_size_visible_across_threads'],
    'A4': ['ConcurrencyTest.test_expiry_thread_responsiveness',
           'ExpiryTest.test_condvar_notification_not_lost'],
    'A5': ['SourceCheckTest.test_server_accepting_is_atomic',
           'ConcurrencyTest.test_accepting_flag_thread_safe'],
    'B1': ['SecurityTest.test_parse_raw_buffer_overflow_protection',
           'ParserTest.test_parse_raw_validates_command_length'],
    'B2': ['UBDetectionTest.test_string_view_return_type_safe',
           'ValueTest.test_string_view_not_dangling_after_move'],
    'B3': ['MemoryPoolTest.test_pointers_stable_after_growth'],
    'B4': ['MemoryPoolTest.test_no_double_free_on_copy'],
    'C1': ['SecurityTest.test_connection_no_reference_cycle'],
    'C2': ['EvictionTest.test_lru_touch_no_iterator_invalidation'],
    'C3': ['SourceCheckTest.test_get_buffer_returns_const',
           'SecurityTest.test_unique_ptr_get_no_double_delete'],
    'C4': ['SourceCheckTest.test_snapshot_uses_make_unique',
           'SnapshotTest.test_save_snapshot_exception_safety'],
    'D1': ['SourceCheckTest.test_no_use_after_move_in_enqueue',
           'ReplicationTest.test_enqueue_no_use_after_move_in_log',
           'ReplicationTest.test_enqueue_logs_correct_key'],
    'D2': ['UBDetectionTest.test_fast_integer_parse_no_strict_aliasing_violation',
           'ValueTest.test_fast_integer_parse_no_aliasing_violation'],
    'D3': ['UBDetectionTest.test_sequence_counter_type_is_unsigned',
           'ReplicationTest.test_sequence_number_no_overflow'],
    'D4': ['UBDetectionTest.test_make_moved_value_actually_moves',
           'ValueTest.test_make_moved_value_actually_moves'],
    'E1': ['SecurityTest.test_ttl_overflow_protection',
           'ExpiryTest.test_large_ttl_no_integer_overflow'],
    'E2': ['SourceCheckTest.test_no_user_data_as_format_string',
           'SecurityTest.test_log_does_not_use_user_data_as_format_string'],
    'E3': ['SecurityTest.test_extract_key_no_overread'],
    'E4': ['SecurityTest.test_key_length_limit'],
}

# ==============================================================================
# Bug dependency graph (chains for RL exploration/exploitation)
# ==============================================================================
BUG_DEPENDENCIES = {
    # Chain 1: L1 build fix -> setup -> deadlock -> memory pool
    'A2': ['L1'],       # deadlock tests need config setup
    'B3': ['A2'],       # memory pool stability needs lock ordering fixed
    'B4': ['B3'],       # double-free check needs stable pool
    # Chain 2: setup -> eviction -> expiry
    'C2': ['L1'],       # eviction needs working config
    'A4': ['C2'],       # expiry condvar needs eviction iterator safety
    'E1': ['A4'],       # TTL overflow needs working expiry
    # Chain 3: parser -> security
    'E3': ['B1'],       # buffer overread fix needs safe parser length
    'E4': ['E3'],       # key length limit needs safe extract_key
    # Chain 4: setup -> server integration
    'L4': ['L1'],       # include guard needs config setup
    'A1': ['L4'],       # connection sync needs both headers
    'A5': ['A1'],       # atomic accepting_ needs sync pattern
    'C1': ['L4'],       # shared_ptr cycle needs connection.h
    # Chain 5: data types -> replication
    'D2': ['L1'],       # fast parse needs config
    'D1': ['D2'],       # use-after-move fix after data types stable
    'D3': ['D1'],       # sequence counter after move semantics
    # Chain 6: RAII/smart pointers
    'C4': ['L1'],       # make_unique needs build working
    'C3': ['C4'],       # const correctness after ownership fixed
    # Independent
    'D4': ['L1'],       # make_moved_value needs build
    'B2': ['D4'],       # string_view safety after move semantics
    'E2': ['L4'],       # format string needs connection.h
    'L2': [],           # signal handler is independent
    'L3': [],           # port parsing is independent
}
