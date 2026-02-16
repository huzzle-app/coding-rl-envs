const PASS_THRESHOLDS = [0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0];
const THRESHOLD_REWARDS = [0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0];

const TOTAL_BUGS = 1260;
const TOTAL_TESTS = 11893;

function sparseReward(passRate) {
  for (let i = PASS_THRESHOLDS.length - 1; i >= 0; i -= 1) {
    if (passRate >= PASS_THRESHOLDS[i]) return THRESHOLD_REWARDS[i];
  }
  return 0.0;
}

function totalBugs() {
  return TOTAL_BUGS;
}

function totalTests() {
  return TOTAL_TESTS;
}

module.exports = {
  PASS_THRESHOLDS,
  THRESHOLD_REWARDS,
  sparseReward,
  totalBugs,
  totalTests
};
