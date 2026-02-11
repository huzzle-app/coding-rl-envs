/**
 * CollabCanvas Reward Calculator
 *
 * Sparse reward function matching TalentFlow pattern
 */

// Test category weights
const CATEGORY_WEIGHTS = {
  unit: 1.0,
  integration: 1.5,
  system: 2.5,
  security: 2.0
};

// Sparse reward thresholds
const PASS_THRESHOLDS = [0.25, 0.50, 0.75, 0.90, 1.0];
const THRESHOLD_REWARDS = [0.0, 0.15, 0.35, 0.65, 1.0];

class RewardCalculator {
  constructor() {
    this.regressionPenalty = -0.15;
    this.categoryCompletionBonus = 0.05;
    this.bugBonus = 0.15;
    this.efficiencyBonus = 0.05;
  }

  /**
   * Calculate total reward
   */
  calculateReward(testResults, previousResults = null, stepCount = 0, maxSteps = 100) {
    const passRate = testResults.passRate || 0;

    // Component 1: Test pass score (60%) - sparse thresholds
    const testPassScore = this._calculateSparseReward(passRate) * 0.60;

    // Component 2: Category completion bonus (20%)
    const completionBonus = this._calculateCategoryBonus(testResults);

    // Component 3: Bug fix bonus (15%)
    const bugFixBonus = this._calculateBugBonus(testResults);

    // Component 4: Efficiency bonus (5%) - only if all pass
    const efficiency = passRate >= 1.0
      ? Math.max(0, (1 - stepCount / maxSteps)) * this.efficiencyBonus
      : 0;

    // Regression penalty
    const regression = this._calculateRegressionPenalty(testResults, previousResults);

    const total = testPassScore + completionBonus + bugFixBonus + efficiency + regression;

    return Math.max(-1.0, Math.min(1.0, total));
  }

  /**
   * Calculate sparse threshold reward
   */
  _calculateSparseReward(passRate) {
    let reward = 0;
    for (let i = 0; i < PASS_THRESHOLDS.length; i++) {
      if (passRate >= PASS_THRESHOLDS[i]) {
        reward = THRESHOLD_REWARDS[i];
      } else {
        break;
      }
    }
    return reward;
  }

  /**
   * Calculate category completion bonus
   */
  _calculateCategoryBonus(testResults) {
    if (!testResults.testSuites) return 0;

    let completedCategories = 0;
    const categories = { unit: true, integration: true, system: true, security: true };

    for (const suite of testResults.testSuites) {
      const category = this._getSuiteCategory(suite.name);
      if (category && !suite.passed) {
        categories[category] = false;
      }
    }

    for (const [cat, complete] of Object.entries(categories)) {
      if (complete) completedCategories++;
    }

    // Need at least 2 categories complete for any bonus
    if (completedCategories < 2) return 0;

    return Math.min((completedCategories - 1) * this.categoryCompletionBonus, 0.20);
  }

  /**
   * Calculate bug fix bonus
   */
  _calculateBugBonus(testResults) {
    return 0;
  }

  /**
   * Count fixed bugs based on test results
   */
  countFixedBugs(testResults) {
    return 0;
  }

  /**
   * Calculate regression penalty
   */
  _calculateRegressionPenalty(current, previous) {
    if (!previous) return 0;

    const currentPassed = current.passed || 0;
    const previousPassed = previous.passed || 0;

    if (currentPassed < previousPassed) {
      const regressions = previousPassed - currentPassed;
      return this.regressionPenalty * (regressions / Math.max(previousPassed, 1));
    }

    return 0;
  }

  /**
   * Get test suite category from path
   */
  _getSuiteCategory(suitePath) {
    if (suitePath.includes('/unit/')) return 'unit';
    if (suitePath.includes('/integration/')) return 'integration';
    if (suitePath.includes('/system/')) return 'system';
    if (suitePath.includes('/security/')) return 'security';
    return null;
  }
}

module.exports = RewardCalculator;
