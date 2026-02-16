const PASS_THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0];
const THRESHOLD_REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0];

function sparseReward(passRate) {
  for (let i = PASS_THRESHOLDS.length - 1; i >= 0; i -= 1) {
    if (passRate >= PASS_THRESHOLDS[i]) return THRESHOLD_REWARDS[i];
  }
  return 0.0;
}

function totalBugs() { return 57; }
function totalTests() { return 9040; }

module.exports = {
  PASS_THRESHOLDS,
  THRESHOLD_REWARDS,
  sparseReward,
  totalBugs,
  totalTests
};
