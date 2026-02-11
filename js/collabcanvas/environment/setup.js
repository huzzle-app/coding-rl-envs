/**
 * CollabCanvas RL Environment Setup
 *
 * Gym-like interface for RL training
 */

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const RewardCalculator = require('./reward');
const { BUG_TEST_MAPPING, BUG_CATEGORIES } = require('./reward');

const PROJECT_ROOT = path.dirname(__dirname);

class CollabCanvasEnvironment {
  /**
   * Observation space definition (Gymnasium-compatible schema).
   *
   * Observations include test results, reward, step count, action result,
   * and a per-bug boolean map indicating which bugs remain.
   */
  static observationSpace = {
    type: 'Dict',
    spaces: {
      testResults: {
        type: 'Dict',
        keys: ['total', 'passed', 'failed', 'passRate', 'passedTests', 'failedTests'],
      },
      reward: { type: 'Box', low: -1.0, high: 1.0, shape: [1] },
      stepCount: { type: 'Discrete', n: 101 },
      actionResult: { type: 'Dict' },
      bugsRemaining: { type: 'MultiBinary', n: 25 },
    },
  };

  /**
   * Action space definition (Gymnasium-compatible schema).
   *
   * Actions are dictionaries with a type field and associated parameters.
   */
  static actionSpace = {
    type: 'Dict',
    spaces: {
      type: { type: 'Discrete', values: ['edit', 'read', 'run_command'] },
      filePath: { type: 'Text', maxLength: 256 },
      content: { type: 'Text', maxLength: 100000 },
      oldContent: { type: 'Text', maxLength: 100000 },
      newContent: { type: 'Text', maxLength: 100000 },
      command: { type: 'Text', maxLength: 1000 },
    },
  };

  /**
   * File-to-test mapping for targeted test runs.
   *
   * When a file in a given source directory is edited, only the relevant
   * test files are executed for fast feedback before the next full-suite run.
   */
  static FILE_TEST_MAP = {
    'src/services/canvas/crdt': ['tests/unit/services/crdt.service.test.js'],
    'src/services/canvas/sync': ['tests/unit/services/sync.service.test.js', 'tests/integration/websocket/sync.test.js'],
    'src/services/canvas/history': ['tests/unit/services/history.service.test.js'],
    'src/services/collaboration/broadcast': ['tests/unit/services/broadcast.service.test.js'],
    'src/services/collaboration/presence': ['tests/unit/services/presence.service.test.js', 'tests/integration/websocket/presence.integration.test.js'],
    'src/services/board/board': ['tests/integration/database/board.integration.test.js', 'tests/integration/routes/board.routes.test.js'],
    'src/services/board/permission': ['tests/unit/services/permission.service.test.js'],
    'src/services/auth/jwt': ['tests/unit/services/jwt.service.test.js', 'tests/security/auth.security.test.js'],
    'src/services/auth/oauth': ['tests/unit/services/oauth.service.test.js', 'tests/security/auth.security.test.js'],
    'src/services/storage/upload': ['tests/security/upload.security.test.js'],
    'src/config/': ['tests/unit/config/database.config.test.js', 'tests/system/startup.system.test.js'],
    'src/middleware/': ['tests/unit/middleware/auth.middleware.test.js'],
    'src/websocket/': ['tests/integration/websocket/sync.test.js', 'tests/integration/websocket/presence.integration.test.js', 'tests/security/websocket.security.test.js'],
    'src/models/': ['tests/unit/models/board.model.test.js', 'tests/unit/models/element.model.test.js'],
    'package.json': ['tests/system/startup.system.test.js'],
  };

  constructor(options = {}) {
    this.maxSteps = options.maxSteps || 100;
    this.timeout = options.timeout || 300; // seconds
    this.projectRoot = PROJECT_ROOT;

    this.stepCount = 0;
    this.previousResults = null;
    this.rewardCalculator = new RewardCalculator();

    this._fullRunInterval = 3;
    this._stepsSinceFullRun = 0;
  }

  /**
   * Validate an action before execution.
   *
   * @param {Object} action - The action to validate
   * @returns {null|Object} null if valid, or an error object if invalid
   */
  validateAction(action) {
    if (!action || typeof action !== 'object') {
      return { success: false, error: 'Action must be a non-null object' };
    }

    const actionType = action.type;
    if (!['edit', 'read', 'run_command'].includes(actionType)) {
      return { success: false, error: `Invalid action type: ${actionType}` };
    }

    if (actionType === 'edit' || actionType === 'read') {
      const filePath = action.filePath || '';
      if (typeof filePath !== 'string' || filePath.length > 256) {
        return { success: false, error: 'File path must be a string of at most 256 characters' };
      }
      if (filePath.includes('..')) {
        return { success: false, error: 'Path traversal not allowed' };
      }
      if (path.isAbsolute(filePath)) {
        return { success: false, error: 'Absolute paths not allowed' };
      }
      const resolved = path.resolve(this.projectRoot, filePath);
      if (!resolved.startsWith(path.resolve(this.projectRoot))) {
        return { success: false, error: 'Path escapes project directory' };
      }
    }

    if (actionType === 'edit') {
      const filePath = action.filePath || '';
      // Reject edits to test files
      if (
        filePath.startsWith('test/') ||
        filePath.startsWith('tests/') ||
        filePath.startsWith('__tests__/') ||
        /\.(test|spec)\.[jt]s$/.test(filePath)
      ) {
        return { success: false, error: 'Editing test files is not allowed' };
      }
      const content = action.content || '';
      const oldContent = action.oldContent || '';
      const newContent = action.newContent || '';
      if (content.length > 100000 || oldContent.length > 100000 || newContent.length > 100000) {
        return { success: false, error: 'Content exceeds 100K character limit' };
      }
    }

    if (actionType === 'run_command') {
      const command = action.command || '';
      if (typeof command !== 'string' || command.length > 1000) {
        return { success: false, error: 'Command must be a string of at most 1000 characters' };
      }
    }

    return null;
  }

  /**
   * Reset environment to initial buggy state
   */
  async reset() {
    this.stepCount = 0;
    this.previousResults = null;
    this._stepsSinceFullRun = 0;

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

    // Validate action first
    const validationError = this.validateAction(action);
    if (validationError) {
      return {
        observation: {
          testResults: this.previousResults || { total: 0, passed: 0, failed: 0, passRate: 0 },
          actionResult: validationError,
          stepCount: this.stepCount,
        },
        reward: 0,
        done: this.stepCount >= this.maxSteps,
        truncated: this.stepCount >= this.maxSteps,
        info: { bugsFixed: 0, totalBugs: 25 },
      };
    }

    // Execute action based on type
    let actionResult;
    try {
      switch (action.type) {
        case 'edit':
          actionResult = await this.executeEdit(action);
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

    // Determine which tests to run
    let testResults;
    const isMutating = action.type === 'edit' || action.type === 'run_command';

    if (isMutating) {
      this._stepsSinceFullRun++;
      const changedFile = action.filePath || '';

      // Run targeted tests first for instant feedback
      const targetedResults = changedFile ? await this.runTargetedTests(changedFile) : null;

      // Full suite every _fullRunInterval mutating steps, or if all targeted pass
      const allTargetedPass = targetedResults && targetedResults.passRate === 1.0;
      if (this._stepsSinceFullRun >= this._fullRunInterval || allTargetedPass || !targetedResults) {
        testResults = await this.runTests();
        testResults._isFullRun = true;
        this._stepsSinceFullRun = 0;
      } else {
        testResults = targetedResults;
      }
    } else {
      testResults = this.previousResults || await this.runTests();
    }

    // Calculate reward
    const reward = this.rewardCalculator.calculateReward(
      testResults,
      this.previousResults,
      this.stepCount,
      this.maxSteps
    );

    this.previousResults = testResults;

    // Check if done — only on full suite runs with actual results
    const isFullRun = !!testResults._isFullRun;
    const hasResults = (testResults.total || 0) > 0;
    const done = (isFullRun && hasResults && testResults.passRate === 1.0) || this.stepCount >= this.maxSteps;
    const truncated = this.stepCount >= this.maxSteps && testResults.passRate < 1.0;

    return {
      observation: {
        testResults,
        actionResult,
        stepCount: this.stepCount,
        bugsRemaining: this.countRemainingBugs(testResults),
      },
      reward,
      done,
      truncated,
      info: {
        bugsFixed: this.rewardCalculator.countFixedBugs(testResults),
        totalBugs: 25,
      },
    };
  }

  /**
   * Execute file edit action
   */
  async executeEdit(action) {
    const { filePath, content, oldContent, newContent } = action;
    const fullPath = path.resolve(this.projectRoot, filePath);
    if (!fullPath.startsWith(path.resolve(this.projectRoot))) {
      return { success: false, error: 'Path escapes project directory' };
    }

    if (content !== undefined) {
      // Full file replacement
      await fs.promises.writeFile(fullPath, content, 'utf-8');
    } else if (oldContent !== undefined && newContent !== undefined) {
      // String replacement
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
    if (!fullPath.startsWith(path.resolve(this.projectRoot))) {
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

    // Parse command into args
    const args = command.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g);
    if (!args || args.length === 0) {
      return { success: false, error: 'Empty command' };
    }

    const safeCommands = new Set(['npx', 'npm', 'node', 'cat', 'ls', 'grep', 'find', 'head', 'tail']);
    const cmd = args[0];
    if (!safeCommands.has(cmd)) {
      return { success: false, error: `Command '${cmd}' not allowed` };
    }

    const dangerousArgs = new Set(['--delete', 'rm', 'eval', 'exec', '--system']);
    for (const arg of args.slice(1)) {
      if (dangerousArgs.has(arg)) {
        return { success: false, error: 'Dangerous argument blocked' };
      }
    }

    try {
      const { execFileSync } = require('child_process');
      const output = execFileSync(cmd, args.slice(1), {
        cwd: this.projectRoot,
        encoding: 'utf-8',
        timeout: 60000,
      });
      return { success: true, output };
    } catch (error) {
      return { success: false, error: error.message, output: error.stdout };
    }
  }

  /**
   * Run targeted tests for a specific changed file.
   *
   * Uses FILE_TEST_MAP to find the subset of test files relevant to
   * the changed source file, providing fast feedback.
   *
   * @param {string} changedFile - Relative path to the changed file
   * @returns {Object|null} Test results from the targeted run, or null if no mapping found
   */
  async runTargetedTests(changedFile) {
    const testFiles = new Set();

    for (const [prefix, tests] of Object.entries(CollabCanvasEnvironment.FILE_TEST_MAP)) {
      if (changedFile.startsWith(prefix) || changedFile === prefix) {
        for (const t of tests) {
          testFiles.add(t);
        }
      }
    }

    if (testFiles.size === 0) {
      return null;
    }

    const testPathArgs = [...testFiles].join(' ');

    try {
      const result = execSync(
        `npx jest --json --testLocationInResults ${testPathArgs}`,
        {
          cwd: this.projectRoot,
          encoding: 'utf-8',
          timeout: this.timeout * 1000,
        }
      );
      return this.parseTestResults(result);
    } catch (error) {
      if (error.stdout) {
        return this.parseTestResults(error.stdout);
      }
      return null;
    }
  }

  /**
   * Run full test suite
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
      // Jest returns non-zero exit code on test failures
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
      // Find JSON in output
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
   * Get list of bug descriptions
   */
  getBugDescriptions() {
    return {
      A1: 'Missing await on Redis publish in broadcast service',
      A2: 'Race condition in sync service - no locking for concurrent updates',
      A3: 'Memory leak - event listeners not removed on disconnect',
      A4: 'Stale closure in presence handler captures old board reference',
      A5: 'Event loop blocking with synchronous JSON operations',
      B1: 'CRDT vector clock comparison uses string comparison',
      B2: 'Shallow copy in mergeState loses nested properties',
      B3: 'Prototype pollution vulnerability in mergeState',
      B4: 'Undo stack stores references instead of copies',
      C1: 'Missing transaction wrapper in board creation',
      C2: 'Permission check race condition (check-then-act)',
      C3: 'Redis connection leak in cache service',
      C4: 'N+1 query in board loading',
      D1: 'JWT_SECRET from env without validation',
      D2: 'OAuth state parameter not validated (CSRF vulnerability)',
      D3: 'Arrow function loses this context in permission checker',
      D4: 'Socket auth middleware timing issue',
      E1: 'Path traversal vulnerability in file upload',
      E2: 'File size checked after reading into memory',
      E3: 'Callback-style error handling loses errors',
      E4: 'Only MIME type checked, not file extension',
      F1: 'Conflicting package versions in package.json',
      F2: 'Circular import between config files',
      F3: 'Missing await on database sync in server startup',
      F4: 'Environment variable type coercion (string vs number)',
    };
  }

  /**
   * Get per-bug remaining status
   */
  countRemainingBugs(testResults) {
    const bugs = {};
    if (!testResults || !testResults.testSuites) {
      for (const bugId of Object.keys(BUG_TEST_MAPPING)) {
        bugs[bugId] = true;
      }
      return bugs;
    }

    const passingTests = new Set();
    for (const suite of testResults.testSuites) {
      for (const test of suite.tests || []) {
        if (test.passed) {
          passingTests.add(test.name);
        }
      }
    }

    for (const [bugId, testNames] of Object.entries(BUG_TEST_MAPPING)) {
      const allPass = testNames.every(name =>
        [...passingTests].some(t => t.includes(name))
      );
      bugs[bugId] = !allPass; // true if bug still exists
    }

    return bugs;
  }

  /**
   * Get project file structure
   */
  getProjectStructure() {
    const files = [];
    const walk = (dir, prefix = '') => {
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
    };

    walk('src');
    walk('tests');

    return files;
  }

  /**
   * Get success criteria description
   */
  getSuccessCriteria() {
    return 'All 125 Jest tests must pass. Fix all 25 intentional bugs across 6 categories: WebSocket & Real-time (A), State Management (B), Database & Transactions (C), Authentication (D), File Handling (E), and Configuration (F).';
  }

  /**
   * Get setup-specific bug IDs
   */
  getSetupBugs() {
    return BUG_CATEGORIES.config || [];
  }

  /**
   * Gymnasium-compatible step returning [obs, reward, done, truncated, info]
   */
  async gymStep(action) {
    const result = await this.step(action);
    return [result.observation, result.reward, result.done, result.truncated, result.info];
  }
}

module.exports = CollabCanvasEnvironment;
