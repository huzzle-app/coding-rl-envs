/**
 * MediaFlow RL Environment Setup
 *
 * Gym-like interface for RL training
 */

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const RewardCalculator = require('./reward');

const PROJECT_ROOT = path.dirname(__dirname);

// File-to-test mapping: maps source files to their relevant test files
const FILE_TEST_MAPPING = {
  // Shared modules
  'shared/clients.js': ['tests/unit/shared/clients.test.js', 'tests/system/startup.test.js'],
  'shared/events.js': ['tests/system/distributed.test.js', 'tests/unit/catalog/events.test.js'],
  'shared/utils.js': ['tests/chaos/distributed.test.js', 'tests/system/distributed.test.js'],
  'shared/config.js': ['tests/system/startup.test.js'],
  'shared/index.js': ['tests/system/startup.test.js'],

  // Gateway service
  'services/gateway/src/index.js': ['tests/integration/gateway.test.js'],
  'services/gateway/src/services/registry.js': ['tests/unit/gateway/routing.test.js'],
  'services/gateway/src/services/router.js': ['tests/unit/gateway/routing.test.js'],
  'services/gateway/src/middleware/auth.js': ['tests/unit/gateway/middleware.test.js'],
  'services/gateway/src/middleware/proxy.js': ['tests/unit/gateway/middleware.test.js'],
  'services/gateway/src/middleware/error.js': ['tests/unit/gateway/middleware.test.js'],
  'services/gateway/src/middleware/cors.js': ['tests/unit/gateway/middleware.test.js'],
  'services/gateway/src/middleware/ratelimit.js': ['tests/unit/gateway/routing.test.js'],

  // Auth service
  'services/auth/src/index.js': ['tests/integration/auth.test.js', 'tests/unit/auth/jwt.test.js'],

  // Users service
  'services/users/src/index.js': ['tests/unit/users.test.js', 'tests/integration/users.test.js'],

  // Upload service
  'services/upload/src/index.js': ['tests/integration/upload.test.js'],

  // Transcode service
  'services/transcode/src/services/bitrate.js': ['tests/unit/transcode/bitrate.test.js'],
  'services/transcode/src/services/transcode.js': ['tests/unit/transcode/transcode.test.js'],
  'services/transcode/src/worker.js': ['tests/unit/transcode/transcode.test.js'],

  // Catalog service
  'services/catalog/src/services/catalog.js': ['tests/unit/catalog/video.test.js', 'tests/integration/catalog.test.js'],
  'services/catalog/src/services/search.js': ['tests/unit/catalog/video.test.js', 'tests/integration/catalog.test.js', 'tests/security/injection.test.js'],
  'services/catalog/src/services/events.js': ['tests/unit/catalog/events.test.js', 'tests/integration/catalog.test.js'],

  // Streaming service
  'services/streaming/src/services/hls.js': ['tests/unit/streaming/hls.test.js', 'tests/integration/streaming.test.js'],
  'services/streaming/src/services/cdn.js': ['tests/unit/streaming/cdn.test.js', 'tests/integration/streaming.test.js', 'tests/integration/cache.test.js'],
  'services/streaming/src/services/cache.js': ['tests/unit/streaming/cdn.test.js', 'tests/integration/cache.test.js'],
  'services/streaming/src/services/storage.js': ['tests/unit/streaming/hls.test.js', 'tests/integration/streaming.test.js'],

  // Billing service
  'services/billing/src/services/subscription.js': ['tests/unit/billing/subscription.test.js', 'tests/integration/billing.test.js'],
  'services/billing/src/services/usage.js': ['tests/integration/billing.test.js'],
  'services/billing/src/webhooks.js': ['tests/integration/billing.test.js'],

  // Recommendations service
  'services/recommendations/src/index.js': ['tests/unit/recommendations.test.js', 'tests/integration/recommendations.test.js'],

  // Analytics service
  'services/analytics/src/index.js': ['tests/unit/analytics.test.js', 'tests/integration/analytics.test.js'],
};

class MediaFlowEnvironment {
  /**
   * Observation space definition for RL agents
   */
  static get observation_space() {
    return {
      type: 'Dict',
      spaces: {
        test_results: {
          type: 'Dict',
          spaces: {
            total: { type: 'Discrete', n: 600, description: 'Total test count' },
            passed: { type: 'Discrete', n: 600, description: 'Passing test count' },
            failed: { type: 'Discrete', n: 600, description: 'Failing test count' },
            pass_rate: { type: 'Box', low: 0.0, high: 1.0, shape: [1], description: 'Test pass rate' },
          },
        },
        step_count: { type: 'Discrete', n: 201, description: 'Current step number' },
        bugs_fixed: { type: 'Discrete', n: 91, description: 'Number of bugs confirmed fixed' },
        total_bugs: { type: 'Discrete', n: 91, description: 'Total bug count (90)' },
        action_result: {
          type: 'Dict',
          spaces: {
            success: { type: 'Discrete', n: 2, description: 'Action success boolean' },
            output: { type: 'Text', max_length: 100000, description: 'Action output text' },
            error: { type: 'Text', max_length: 10000, description: 'Error message if any' },
          },
        },
        file_list: { type: 'Sequence', element: { type: 'Text' }, description: 'Source file paths' },
      },
    };
  }

  /**
   * Action space definition for RL agents
   */
  static get action_space() {
    return {
      type: 'Dict',
      spaces: {
        type: {
          type: 'Discrete',
          n: 3,
          values: ['edit', 'read', 'run_command'],
          description: 'Action type to perform',
        },
        filePath: {
          type: 'Text',
          max_length: 500,
          description: 'File path (relative to project root) for edit/read actions',
        },
        content: {
          type: 'Text',
          max_length: 1000000,
          description: 'Full file content for edit action (overwrites entire file)',
        },
        oldContent: {
          type: 'Text',
          max_length: 100000,
          description: 'Content to replace for edit action (string replacement)',
        },
        newContent: {
          type: 'Text',
          max_length: 100000,
          description: 'Replacement content for edit action (string replacement)',
        },
        command: {
          type: 'Text',
          max_length: 5000,
          description: 'Shell command for run_command action',
        },
      },
    };
  }

  constructor(options = {}) {
    this.maxSteps = options.maxSteps || 200;
    this.timeout = options.timeout || 600; // 10 minutes
    this.projectRoot = PROJECT_ROOT;

    this.stepCount = 0;
    this.previousResults = null;
    this.rewardCalculator = new RewardCalculator();
    this.fileTestMapping = FILE_TEST_MAPPING;
  }

  /**
   * Validate an action before execution
   * @param {Object} action - The action to validate
   * @returns {{ valid: boolean, error?: string }} Validation result
   */
  validateAction(action) {
    if (!action || typeof action !== 'object') {
      return { valid: false, error: 'Action must be a non-null object' };
    }

    const validTypes = ['edit', 'read', 'run_command'];
    if (!validTypes.includes(action.type)) {
      return { valid: false, error: `Invalid action type: ${action.type}. Must be one of: ${validTypes.join(', ')}` };
    }

    if (action.type === 'edit') {
      if (!action.filePath) {
        return { valid: false, error: 'Edit action requires filePath' };
      }
      if (action.content === undefined && (action.oldContent === undefined || action.newContent === undefined)) {
        return { valid: false, error: 'Edit action requires either content (full replace) or both oldContent and newContent (partial replace)' };
      }
      // Prevent editing test infrastructure
      if (action.filePath.startsWith('environment/') && !action.filePath.includes('__pycache__')) {
        return { valid: false, error: 'Cannot modify environment wrapper files' };
      }
      // Reject edits to test files
      if (
        action.filePath.startsWith('test/') ||
        action.filePath.startsWith('tests/') ||
        action.filePath.startsWith('__tests__/') ||
        /\.(test|spec)\.[jt]s$/.test(action.filePath)
      ) {
        return { valid: false, error: 'Editing test files is not allowed' };
      }
      // Validate file path is within project
      const fullPath = path.resolve(this.projectRoot, action.filePath);
      if (!fullPath.startsWith(path.resolve(this.projectRoot) + path.sep)) {
        return { valid: false, error: 'File path must be within project directory' };
      }
    }

    if (action.type === 'read') {
      if (!action.filePath) {
        return { valid: false, error: 'Read action requires filePath' };
      }
      const readFullPath = path.resolve(this.projectRoot, action.filePath);
      if (!readFullPath.startsWith(path.resolve(this.projectRoot) + path.sep)) {
        return { valid: false, error: 'File path must be within project directory' };
      }
    }

    if (action.type === 'run_command') {
      if (!action.command) {
        return { valid: false, error: 'run_command action requires command' };
      }
      // Allowlist-based command validation
      const args = action.command.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g);
      if (!args || args.length === 0) {
        return { valid: false, error: 'Empty command' };
      }
      const safeCommands = new Set(['npx', 'npm', 'node', 'cat', 'ls', 'grep', 'find', 'head', 'tail', 'docker']);
      if (!safeCommands.has(args[0])) {
        return { valid: false, error: `Command '${args[0]}' not allowed` };
      }
      const dangerousArgs = new Set(['--delete', 'rm', 'eval', 'exec', '--system']);
      for (const arg of args.slice(1)) {
        if (dangerousArgs.has(arg)) {
          return { valid: false, error: 'Dangerous argument blocked' };
        }
      }
    }

    return { valid: true };
  }

  /**
   * Get test files relevant to a changed source file
   * @param {string} filePath - Source file path relative to project root
   * @returns {string[]} Relevant test file paths
   */
  getTestsForFile(filePath) {
    // Direct mapping
    if (this.fileTestMapping[filePath]) {
      return this.fileTestMapping[filePath];
    }

    // Try to match by directory
    const results = [];
    for (const [srcFile, testFiles] of Object.entries(this.fileTestMapping)) {
      if (filePath.startsWith(path.dirname(srcFile))) {
        results.push(...testFiles);
      }
    }

    return [...new Set(results)];
  }

  /**
   * Run targeted tests for specific file(s) instead of the full suite
   * @param {string|string[]} testPaths - Test file path(s) relative to project root
   * @returns {Object} Test results
   */
  async runTargetedTests(testPaths) {
    const paths = Array.isArray(testPaths) ? testPaths : [testPaths];
    const testArgs = paths.map(p => path.join(this.projectRoot, p)).join(' ');

    try {
      const result = execSync(
        `npx jest --json --testLocationInResults ${testArgs}`,
        {
          cwd: this.projectRoot,
          encoding: 'utf-8',
          timeout: 120000,
        }
      );
      return this.parseTestResults(result);
    } catch (error) {
      if (error.stdout) {
        return this.parseTestResults(error.stdout);
      }
      return {
        total: 0,
        passed: 0,
        failed: 0,
        passRate: 0,
        error: error.message,
      };
    }
  }

  /**
   * Reset environment to initial buggy state
   */
  async reset() {
    this.stepCount = 0;
    this.previousResults = null;

    // Reset git to initial state
    try {
      execSync('git checkout -- .', {
        cwd: this.projectRoot,
        encoding: 'utf-8',
      });
      execSync('git clean -fd', {
        cwd: this.projectRoot,
        encoding: 'utf-8',
      });
    } catch (error) {
      // Ignore if not a git repo
    }

    const testResults = await this.runTests();

    return {
      testResults,
      reward: 0,
      stepCount: 0,
      bugsRemaining: this.getBugDescriptions(),
      projectStructure: this.getProjectStructure(),
    };
  }

  /**
   * Execute an action and return results
   */
  async step(action) {
    this.stepCount++;

    // Validate action
    const validation = this.validateAction(action);
    if (!validation.valid) {
      return {
        observation: {
          testResults: this.previousResults || { total: 0, passed: 0, failed: 0, passRate: 0 },
          actionResult: { error: validation.error, success: false },
          stepCount: this.stepCount,
        },
        reward: -0.01, // Small penalty for invalid action
        done: this.stepCount >= this.maxSteps,
        truncated: this.stepCount >= this.maxSteps,
        info: {
          bugsFixed: 0,
          totalBugs: 90,
          validationError: validation.error,
        },
      };
    }

    // Execute action based on type
    let actionResult;
    let editedFile = null;
    try {
      switch (action.type) {
        case 'edit':
          actionResult = await this.executeEdit(action);
          editedFile = action.filePath;
          break;
        case 'read':
          actionResult = await this.executeRead(action);
          break;
        case 'run_command':
          actionResult = await this.executeCommand(action);
          break;
        default:
          actionResult = { error: `Unknown action type: ${action.type}` };
      }
    } catch (error) {
      actionResult = { error: error.message };
    }

    // Run targeted tests if we edited a file with known mappings, else run full suite
    let testResults;
    if (editedFile) {
      const relevantTests = this.getTestsForFile(editedFile);
      if (relevantTests.length > 0) {
        // Run targeted tests first for fast feedback
        const targeted = await this.runTargetedTests(relevantTests);
        // Then run full suite for accurate reward calculation
        testResults = await this.runTests();
        actionResult.targetedTests = targeted;
      } else {
        testResults = await this.runTests();
      }
    } else {
      testResults = await this.runTests();
    }

    // Calculate reward
    const reward = this.rewardCalculator.calculateReward(
      testResults,
      this.previousResults,
      this.stepCount,
      this.maxSteps
    );

    this.previousResults = testResults;

    // Check if done — require actual results and full run to prevent empty-suite completion
    const hasResults = (testResults.total || 0) > 0;
    const isFullRun = !!testResults._isFullRun || !editedFile || this.getTestsForFile(editedFile).length === 0;
    const done = (isFullRun && hasResults && testResults.passRate === 1.0) || this.stepCount >= this.maxSteps;
    const truncated = this.stepCount >= this.maxSteps && testResults.passRate < 1.0;

    return {
      observation: {
        testResults,
        actionResult,
        stepCount: this.stepCount,
      },
      reward,
      done,
      truncated,
      info: {
        bugsFixed: this.rewardCalculator.countFixedBugs(testResults),
        totalBugs: 90,
        servicesRunning: this.checkServicesStatus(),
      },
    };
  }

  /**
   * Execute file edit action
   */
  async executeEdit(action) {
    const { filePath, content, oldContent, newContent } = action;
    const fullPath = path.resolve(this.projectRoot, filePath);
    if (!fullPath.startsWith(path.resolve(this.projectRoot) + path.sep)) {
      return { success: false, error: 'Path escapes project directory' };
    }

    if (content !== undefined) {
      await fs.promises.writeFile(fullPath, content, 'utf-8');
    } else if (oldContent !== undefined && newContent !== undefined) {
      const current = await fs.promises.readFile(fullPath, 'utf-8');
      const updated = current.replace(oldContent, newContent);
      await fs.promises.writeFile(fullPath, updated, 'utf-8');
    }

    return { success: true, path: filePath };
  }

  /**
   * Execute file read action
   */
  async executeRead(action) {
    const { filePath } = action;
    const fullPath = path.resolve(this.projectRoot, filePath);
    if (!fullPath.startsWith(path.resolve(this.projectRoot) + path.sep)) {
      return { success: false, error: 'Path escapes project directory' };
    }
    const content = await fs.promises.readFile(fullPath, 'utf-8');
    return { content, path: filePath };
  }

  /**
   * Execute shell command (allowlisted, no shell interpretation)
   */
  async executeCommand(action) {
    const { command } = action;

    const args = command.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g);
    if (!args || args.length === 0) {
      return { success: false, error: 'Empty command' };
    }

    try {
      const { execFileSync } = require('child_process');
      const output = execFileSync(args[0], args.slice(1), {
        cwd: this.projectRoot,
        encoding: 'utf-8',
        timeout: 120000,
      });
      return { success: true, output };
    } catch (error) {
      return { success: false, error: error.message, output: error.stdout };
    }
  }

  /**
   * Run test suite
   */
  async runTests() {
    try {
      const result = execSync('npm test -- --json --testLocationInResults', {
        cwd: this.projectRoot,
        encoding: 'utf-8',
        timeout: this.timeout * 1000,
      });

      return this.parseTestResults(result);
    } catch (error) {
      if (error.stdout) {
        return this.parseTestResults(error.stdout);
      }
      return {
        total: 0,
        passed: 0,
        failed: 0,
        passRate: 0,
        error: error.message,
      };
    }
  }

  /**
   * Parse Jest JSON output
   */
  parseTestResults(output) {
    try {
      const jsonMatch = output.match(/\{[\s\S]*"numTotalTests"[\s\S]*\}/);
      if (!jsonMatch) {
        return this.parseTextOutput(output);
      }

      const json = JSON.parse(jsonMatch[0]);

      return {
        total: json.numTotalTests || 0,
        passed: json.numPassedTests || 0,
        failed: json.numFailedTests || 0,
        passRate: json.numTotalTests > 0
          ? json.numPassedTests / json.numTotalTests
          : 0,
        testSuites: json.testResults?.map(suite => ({
          name: suite.name,
          passed: suite.status === 'passed',
          tests: suite.assertionResults?.map(test => ({
            name: test.fullName,
            passed: test.status === 'passed',
          })) || [],
        })) || [],
      };
    } catch (error) {
      return this.parseTextOutput(output);
    }
  }

  /**
   * Fallback text output parser
   */
  parseTextOutput(output) {
    const passMatch = output.match(/(\d+) pass/i);
    const failMatch = output.match(/(\d+) fail/i);

    const passed = passMatch ? parseInt(passMatch[1], 10) : 0;
    const failed = failMatch ? parseInt(failMatch[1], 10) : 0;
    const total = passed + failed;

    return {
      total,
      passed,
      failed,
      passRate: total > 0 ? passed / total : 0,
    };
  }

  /**
   * Check if services are running (cached for 30 seconds)
   */
  checkServicesStatus() {
    const now = Date.now();
    if (this._servicesCache && (now - this._servicesCacheTime) < 30000) {
      return this._servicesCache;
    }
    try {
      const output = execSync('docker compose ps --format json', {
        cwd: this.projectRoot,
        encoding: 'utf-8',
        timeout: 10000,
      });
      this._servicesCache = JSON.parse(output);
      this._servicesCacheTime = now;
      return this._servicesCache;
    } catch {
      return [];
    }
  }

  /**
   * Get list of bug descriptions
   */
  getBugDescriptions() {
    return {
      // Setup Hell (L)
      L1: 'Circular import between shared modules',
      L2: 'RabbitMQ exchange not declared before binding',
      L3: 'Dead letter exchange not configured',
      L4: 'Service discovery race condition',
      L5: 'Hardcoded service URLs instead of discovery',
      L6: 'Health check misconfiguration',
      L7: 'Watch error silently ignored',
      L8: 'Round-robin counter not thread-safe',
      L9: 'Missing await on async initialization',
      L10: 'Configuration module circular dependency',

      // Distributed Consensus (A)
      A1: 'Distributed lock doesn\'t handle clock skew',
      A2: 'Leader election split-brain',
      A3: 'Lock timeout too short',
      A4: 'Lock release race condition',
      A5: 'Session TTL too short (leader flapping)',
      A6: 'Session expiry not handled',
      A7: 'Watch has no error handling',
      A8: 'No fencing token for leader operations',

      // Event Sourcing (B)
      B1: 'Event ordering not guaranteed',
      B2: 'Idempotency key collision',
      B3: 'Event schema evolution breaks consumers',
      B4: 'Processed events memory leak',
      B5: 'No retry on event processing failure',
      B6: 'Event position tracking gaps',
      B7: 'Projection rebuild race condition',
      B8: 'Concurrent event append race',

      // Service Communication (C)
      C1: 'Circuit breaker threshold off-by-one',
      C2: 'Retry storms (constant delay)',
      C3: 'Request coalescing key collision',

      // Database & Transactions (D)
      D1: 'Saga compensation incomplete',
      D2: 'Saga step dependencies wrong',
      D3: 'Payment idempotency key collision',
      D4: 'Double-charge on retry',
      D5: 'Partial refund calculation errors',

      // Authentication Chain (E)
      E1: 'JWT claims not validated',
      E2: 'Token refresh race condition',
      E3: 'Permission cache stale',
      E4: 'This binding lost in permission checker',

      // Media Processing (F)
      F1: 'Bitrate calculation float precision',
      F2: 'HLS segment duration inconsistency',
      F3: 'Motion factor applied incorrectly',
      F4: 'VBV buffer overflow for 4K',
      F5: 'HDR metadata validation incomplete',
      F6: 'Discontinuity tag position wrong',
      F7: 'Keyframe alignment issues',
      F8: 'Live edge calculation wrong',

      // Billing Logic (G)
      G1: 'Subscription upgrade race condition',
      G2: 'Proration calculation precision errors',
      G3: 'Currency precision loss',
      G4: 'Grace period not handled',
      G5: 'Subscription status check incomplete',
      G6: 'Tax calculation rounding errors',

      // Caching & CDN (H)
      H1: 'Cache stampede on popular content',
      H2: 'Hot key concentration',
      H3: 'CDN purge race condition',
      H4: 'No TTL jitter (thundering herd)',
      H5: 'Write-through not atomic',
      H6: 'Edge cache inconsistency',

      // Security (I)
      I1: 'SQL injection in search',
      I2: 'Rate limit bypass via X-Forwarded-For',
      I3: 'CORS allows all origins',
      I4: 'SSRF in thumbnail proxy',
      I5: 'SSRF in webhook handler',
      I6: 'Stack trace exposed',
      I7: 'NoSQL injection in filters',
      I8: 'Regex DoS in autocomplete',

      // Observability (J)
      J1: 'Trace context lost in async',
      J2: 'Correlation ID uses global state',

      // Configuration (K)
      K1: 'Feature flags undefined not false',
      K2: 'JWT_SECRET not validated',
      K3: 'Rate limit string not parsed',
    };
  }

  /**
   * Get project file structure
   */
  getProjectStructure() {
    const files = [];
    const walk = (dir, prefix = '') => {
      try {
        const entries = fs.readdirSync(path.join(this.projectRoot, dir), {
          withFileTypes: true,
        });

        for (const entry of entries) {
          if (entry.name.startsWith('.') || entry.name === 'node_modules') {
            continue;
          }

          const relativePath = path.join(prefix, entry.name);

          if (entry.isDirectory()) {
            walk(path.join(dir, entry.name), relativePath);
          } else if (entry.name.endsWith('.js')) {
            files.push(relativePath);
          }
        }
      } catch {
        // Ignore errors
      }
    };

    walk('services');
    walk('shared');
    walk('tests');

    return files;
  }

  /**
   * Get success criteria description
   */
  getSuccessCriteria() {
    return 'All 537 Jest tests must pass. Fix all 90 intentional bugs across 12 categories in 10 microservices.';
  }

  /**
   * Gymnasium-compatible step returning {observation, reward, done, truncated, info}
   */
  async gymStep(action) {
    const result = await this.step(action);
    return {
      observation: result.observation,
      reward: result.reward,
      done: result.done,
      truncated: result.truncated,
      info: result.info,
    };
  }
}

module.exports = MediaFlowEnvironment;
