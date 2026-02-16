/**
 * MediaFlow Reward Calculator
 *
 * Very sparse reward function for Principal-level difficulty
 */

// Test category weights
const CATEGORY_WEIGHTS = {
  unit: 1.0,
  integration: 1.5,
  contract: 2.0,
  chaos: 3.0,
  security: 2.5,
  performance: 2.0,
  system: 3.0
};

// Very sparse reward thresholds for Principal level
const PASS_THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0];
const THRESHOLD_REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0];

class RewardCalculator {
  constructor() {
    this.regressionPenalty = -0.15;
    this.categoryCompletionBonus = 0.03;
    this.serviceIsolationBonus = 0.02;
    this.chaosTestBonus = 0.10;
    this.bugBonus = 0.10;
    this.efficiencyBonus = 0.05;
  }

  /**
   * Calculate total reward
   */
  calculateReward(testResults, previousResults = null, stepCount = 0, maxSteps = 200) {
    const passRate = testResults.passRate || 0;

    // Component 1: Test pass score (55%) - very sparse thresholds
    const testPassScore = this._calculateSparseReward(passRate) * 0.55;

    // Component 2: Category completion bonus (15%)
    const completionBonus = this._calculateCategoryBonus(testResults);

    // Component 3: Bug fix bonus (15%)
    const bugFixBonus = this._calculateBugBonus(testResults);

    // Component 4: Chaos test bonus (10%)
    const chaosBonus = this._calculateChaosBonus(testResults);

    // Component 5: Efficiency bonus (5%) - only if all pass
    const efficiency = passRate >= 1.0
      ? Math.max(0, (1 - stepCount / maxSteps)) * this.efficiencyBonus
      : 0;

    // Regression penalty
    const regression = this._calculateRegressionPenalty(testResults, previousResults);

    const total = testPassScore + completionBonus + bugFixBonus + chaosBonus + efficiency + regression;

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
    const categories = {
      unit: true,
      integration: true,
      contract: true,
      chaos: true,
      security: true,
      performance: true,
      system: true
    };

    for (const suite of testResults.testSuites) {
      const category = this._getSuiteCategory(suite.name);
      if (category && !suite.passed) {
        categories[category] = false;
      }
    }

    for (const [cat, complete] of Object.entries(categories)) {
      if (complete) completedCategories++;
    }

    if (completedCategories < 3) return 0;

    return Math.min((completedCategories - 2) * this.categoryCompletionBonus, 0.15);
  }

  /**
   * Calculate chaos test bonus
   */
  _calculateChaosBonus(testResults) {
    if (!testResults.testSuites) return 0;

    const chaosSuites = testResults.testSuites.filter(
      s => s.name.includes('/chaos/')
    );

    if (chaosSuites.length === 0) return 0;

    const passedChaos = chaosSuites.filter(s => s.passed).length;
    const passRate = passedChaos / chaosSuites.length;

    return passRate === 1.0 ? this.chaosTestBonus : 0;
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
    if (suitePath.includes('/contract/')) return 'contract';
    if (suitePath.includes('/chaos/')) return 'chaos';
    if (suitePath.includes('/security/')) return 'security';
    if (suitePath.includes('/performance/')) return 'performance';
    if (suitePath.includes('/system/')) return 'system';
    return null;
  }
}

module.exports = RewardCalculator;
