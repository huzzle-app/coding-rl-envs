THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
TOTAL_TESTS = 9546

def sparse_reward(pass_rate: float) -> float:
    for threshold, reward in reversed(list(zip(THRESHOLDS, REWARDS))):
        if pass_rate >= threshold:
            return reward
    return 0.0

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
TOTAL_BUGS = 0  # Legacy stub
