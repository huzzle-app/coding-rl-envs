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

// Sparse reward thresholds (5-threshold Senior tier, matches scoring.py)
const PASS_THRESHOLDS = [0.50, 0.75, 0.90, 1.0];
const THRESHOLD_REWARDS = [0.15, 0.35, 0.65, 1.0];

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

/**
 * Bug-to-test mapping for per-bug status tracking.
 * Keys: bug IDs. Values: arrays of test name substrings that validate the fix.
 */
const BUG_TEST_MAPPING = {
  A1: ['should complete broadcast before returning', 'should await Redis publish'],
  A2: ['should handle concurrent updates', 'race condition'],
  A3: ['should remove heartbeat listener', 'memory leak'],
  A4: ['stale closure', 'should track correct board after switch'],
  A5: ['redundant JSON round-trip', 'should not block event loop'],
  B1: ['should correctly compare vector clock values above 9', 'string/number clock'],
  B2: ['should preserve deeply nested properties', 'partial style update'],
  B3: ['should not merge inherited properties', 'prototype pollution'],
  B4: ['should store deep copies in undo stack'],
  C1: ['should use transaction for board creation', 'transaction for atomicity'],
  C2: ['atomic permission-check-and-remove', 'concurrent permission revocation'],
  C3: ['should close duplicated Redis connections'],
  C4: ['should batch-load elements', 'N+1 queries'],
  D1: ['should fail with undefined JWT_SECRET', 'JWT secret validation'],
  D2: ['should validate OAuth state', 'CSRF'],
  D3: ['should maintain this context in permission checker'],
  D4: ['socket auth timing', 'token expiry correctly'],
  E1: ['path traversal', 'directory traversal'],
  E2: ['file size checked before reading', 'memory'],
  E3: ['should properly propagate errors from image processing'],
  E4: ['should reject executable files', 'file extension'],
  F1: ['socket.io version', 'package version'],
  F2: ['circular import', 'circular dependency'],
  F3: ['missing await on database sync', 'database connection'],
  F4: ['DB_POOL_SIZE', 'environment variable type'],
};

/**
 * Bug categories for grouping and setup detection.
 */
const BUG_CATEGORIES = {
  websocket: ['A1', 'A2', 'A3', 'A4', 'A5'],
  state: ['B1', 'B2', 'B3', 'B4'],
  database: ['C1', 'C2', 'C3', 'C4'],
  auth: ['D1', 'D2', 'D3', 'D4'],
  file: ['E1', 'E2', 'E3', 'E4'],
  config: ['F1', 'F2', 'F3', 'F4'],
};

module.exports = RewardCalculator;
module.exports.BUG_TEST_MAPPING = BUG_TEST_MAPPING;
module.exports.BUG_CATEGORIES = BUG_CATEGORIES;
