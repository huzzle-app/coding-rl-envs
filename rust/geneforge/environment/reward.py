"""GeneForge reward model - sparse reward calculation (Principal, 8-threshold)."""

PASS_THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
THRESHOLD_REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]

TOTAL_TESTS = 1280

def sparse_reward(pass_rate: float) -> float:
    for i in range(len(PASS_THRESHOLDS) - 1, -1, -1):
        if pass_rate >= PASS_THRESHOLDS[i]:
            return THRESHOLD_REWARDS[i]
    return 0.0

def total_tests() -> int:
    return TOTAL_TESTS

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
