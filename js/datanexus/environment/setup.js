/**
 * DataNexus RL Environment Setup
 *
 * Gym-like interface for RL training
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const RewardCalculator = require('./reward');

const PROJECT_ROOT = path.dirname(__dirname);

// File-to-test mapping: maps source files to their relevant test files
const FILE_TEST_MAPPING = {
  // Shared modules
  'shared/index.js': ['tests/system/startup.test.js'],
  'shared/clients/index.js': ['tests/system/startup.test.js', 'tests/integration/pipeline.test.js'],
  'shared/events/index.js': ['tests/system/startup.test.js', 'tests/integration/pipeline.test.js'],
  'shared/utils/index.js': ['tests/chaos/distributed.test.js', 'tests/system/startup.test.js'],
  'shared/stream/index.js': ['tests/unit/stream/windowing.test.js', 'tests/unit/stream/processing.test.js', 'tests/chaos/streaming.test.js'],

  // Gateway service
  'services/gateway/src/index.js': ['tests/integration/pipeline.test.js', 'tests/system/startup.test.js'],
  'services/gateway/src/config.js': ['tests/system/startup.test.js'],
  'services/gateway/src/routes/index.js': ['tests/integration/pipeline.test.js'],
  'services/gateway/src/services/proxy.js': ['tests/integration/pipeline.test.js'],

  // Auth service
  'services/auth/src/index.js': ['tests/integration/pipeline.test.js', 'tests/security/api.test.js'],
  'services/auth/src/services/auth.js': ['tests/security/api.test.js'],

  // Ingestion service
  'services/ingestion/src/index.js': ['tests/integration/pipeline.test.js'],
  'services/ingestion/src/services/ingest.js': ['tests/integration/pipeline.test.js', 'tests/performance/throughput.test.js'],

  // Transform service
  'services/transform/src/index.js': ['tests/unit/transform/pipeline.test.js'],
  'services/transform/src/services/pipeline.js': ['tests/unit/transform/pipeline.test.js', 'tests/security/injection.test.js'],

  // Router service
  'services/router/src/index.js': ['tests/integration/pipeline.test.js'],
  'services/router/src/services/routing.js': ['tests/integration/pipeline.test.js'],

  // Aggregate service
  'services/aggregate/src/index.js': ['tests/unit/aggregate/rollups.test.js'],
  'services/aggregate/src/services/rollups.js': ['tests/unit/aggregate/rollups.test.js', 'tests/chaos/streaming.test.js'],

  // Store service
  'services/store/src/index.js': ['tests/integration/query.test.js'],
  'services/store/src/services/timeseries.js': ['tests/integration/query.test.js', 'tests/performance/throughput.test.js'],

  // Query service
  'services/query/src/index.js': ['tests/unit/query/engine.test.js', 'tests/integration/query.test.js'],
  'services/query/src/services/engine.js': ['tests/unit/query/engine.test.js', 'tests/integration/query.test.js', 'tests/security/injection.test.js'],

  // Alerts service
  'services/alerts/src/index.js': ['tests/unit/alert/detection.test.js', 'tests/integration/alerts.test.js'],
  'services/alerts/src/services/detection.js': ['tests/unit/alert/detection.test.js', 'tests/integration/alerts.test.js'],

  // Dashboards service
  'services/dashboards/src/index.js': ['tests/integration/pipeline.test.js'],
  'services/dashboards/src/services/dashboard.js': ['tests/integration/pipeline.test.js', 'tests/security/injection.test.js'],

  // Connectors service
  'services/connectors/src/index.js': ['tests/unit/connector/framework.test.js'],
  'services/connectors/src/services/framework.js': ['tests/unit/connector/framework.test.js', 'tests/security/api.test.js'],

  // Scheduler service
  'services/scheduler/src/index.js': ['tests/integration/pipeline.test.js'],
  'services/scheduler/src/services/dag.js': ['tests/integration/pipeline.test.js', 'tests/chaos/distributed.test.js'],

  // Workers service
  'services/workers/src/index.js': ['tests/integration/pipeline.test.js'],
  'services/workers/src/services/executor.js': ['tests/integration/pipeline.test.js', 'tests/performance/throughput.test.js'],

  // Admin service
  'services/admin/src/index.js': ['tests/integration/pipeline.test.js'],
  'services/admin/src/services/tenant.js': ['tests/integration/pipeline.test.js', 'tests/security/api.test.js'],

  // Billing service
  'services/billing/src/index.js': ['tests/unit/billing/metering.test.js', 'tests/integration/pipeline.test.js'],
  'services/billing/src/services/metering.js': ['tests/unit/billing/metering.test.js'],
};

class DataNexusEnvironment {
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
            total: { type: 'Discrete', n: 925, description: 'Total test count' },
            passed: { type: 'Discrete', n: 925, description: 'Passing test count' },
            failed: { type: 'Discrete', n: 925, description: 'Failing test count' },
            pass_rate: { type: 'Box', low: 0.0, high: 1.0, shape: [1], description: 'Test pass rate' },
          },
        },
        step_count: { type: 'Discrete', n: 201, description: 'Current step number' },
        bugs_fixed: { type: 'Discrete', n: 121, description: 'Number of bugs confirmed fixed' },
        total_bugs: { type: 'Discrete', n: 121, description: 'Total bug count (120)' },
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
      // Validate content length
      const content = action.content || '';
      const oldContent = action.oldContent || '';
      const newContent = action.newContent || '';
      if (content.length > 100000 || oldContent.length > 100000 || newContent.length > 100000) {
        return { valid: false, error: 'Content exceeds 100K character limit' };
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
          totalBugs: 120,
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

    // Check if done
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
        totalBugs: 120,
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

      const parsed = this.parseTestResults(result);
      parsed._isFullRun = true;
      return parsed;
    } catch (error) {
      if (error.stdout) {
        const parsed = this.parseTestResults(error.stdout);
        parsed._isFullRun = true;
        return parsed;
      }
      return {
        total: 0,
        passed: 0,
        failed: 0,
        passRate: 0,
        error: error.message,
        _isFullRun: true,
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
      // Setup Hell (L) - 15 bugs
      L1: 'Circular import between shared modules',
      L2: 'RabbitMQ exchange not declared before binding',
      L3: 'Missing await on async initialization',
      L4: 'Exchange must be declared before queue binding',
      L5: 'Workspace dependency conflict in package.json',
      L6: 'TimescaleDB extension not created before hypertable',
      L7: 'MinIO bucket policy not applied on startup',
      L8: 'Redis stream consumer group not created before reading',
      L9: 'Worker process fork race condition on startup',
      L10: 'Environment variable type coercion (string vs number)',
      L11: 'CORS preflight OPTIONS not handled before auth middleware',
      L12: 'Logging transport not initialized before first log call',
      L13: 'Schema registry bootstrap fails on empty registry',
      L14: 'Connector plugin loading uses sync require in async path',
      L15: 'Scheduler cron parser not initialized before first job',

      // Stream Processing (A) - 12 bugs
      A1: 'Windowing boundary off-by-one in tumbling window',
      A2: 'Watermark advancement race condition with late arrivals',
      A3: 'Late data handling rejects data for already-closed window',
      A4: 'Exactly-once delivery broken on retry (missing idempotency)',
      A5: 'Event time vs processing time confusion in windowing',
      A6: 'Session window gap merge uses wrong comparison',
      A7: 'Tumbling window overlap at boundary (inclusive both ends)',
      A8: 'Sliding window state not cleaned up (memory leak)',
      A9: 'Stream join ordering bug with misaligned watermarks',
      A10: 'Backpressure propagation delay loses messages',
      A11: 'Partition rebalancing causes data loss during handoff',
      A12: 'Checkpoint barrier timeout too aggressive',

      // Data Transformation (B) - 10 bugs
      B1: 'Schema mapping type coercion silently loses precision',
      B2: 'Null handling in nested fields causes TypeError',
      B3: 'Array flattening depth overflow causes stack overflow',
      B4: 'Regex transform vulnerable to ReDoS',
      B5: 'Date parsing assumes UTC when timezone not specified',
      B6: 'Numeric precision loss in floating-point aggregation',
      B7: 'JSON path expression allows injection of arbitrary paths',
      B8: 'Conditional transform short-circuit evaluates wrong branch',
      B9: 'UDF execution timeout does not clean up resources',
      B10: 'Transform chain ordering dependency not respected',

      // Query Engine (C) - 8 bugs
      C1: 'SQL injection in filter clause via string concatenation',
      C2: 'Query plan cache not invalidated after schema change',
      C3: 'GROUP BY with float equality produces wrong groups',
      C4: 'HAVING clause evaluated before GROUP BY aggregation',
      C5: 'Subquery correlation variable scope leaks to outer query',
      C6: 'LIMIT/OFFSET pagination cursor drifts with concurrent writes',
      C7: 'Time range query boundary inclusive/exclusive mismatch',
      C8: 'Query timeout not propagated to storage layer',

      // Aggregation Pipeline (D) - 10 bugs
      D1: 'Rolling window sum overflows Number.MAX_SAFE_INTEGER',
      D2: 'Time-series downsampling alias loses sub-second precision',
      D3: 'Percentile calculation causes memory spike with large datasets',
      D4: 'Count distinct HyperLogLog merge produces wrong cardinality',
      D5: 'Moving average denominator is zero for empty window',
      D6: 'Rate calculation fails with clock skew between nodes',
      D7: 'Histogram bucket boundary uses float comparison incorrectly',
      D8: 'Top-N tie-breaking is inconsistent across runs',
      D9: 'Running total reset at window boundary off by one',
      D10: 'Cross-stream join watermark alignment causes data loss',

      // Connector Framework (E) - 8 bugs
      E1: 'Source connector offset tracking has gap on restart',
      E2: 'Sink connector delivery guarantee violated on timeout',
      E3: 'Schema registry version conflict on concurrent publish',
      E4: 'Connector task rebalance causes data loss',
      E5: 'Webhook receiver signature validation timing attack',
      E6: 'Connector health check reports healthy when stalled',
      E7: 'Plugin class loading isolation leaks between connectors',
      E8: 'Connector config hot reload race condition',

      // Database & Transactions (F) - 10 bugs
      F1: 'Connection pool exhaustion under concurrent load',
      F2: 'Transaction isolation allows phantom reads',
      F3: 'Saga compensation for multi-step ingest incomplete',
      F4: 'Outbox pattern message ordering violated',
      F5: 'Read replica lag causes stale dashboard data',
      F6: 'Optimistic locking on concurrent pipeline update',
      F7: 'Time-series table partition pruning selects wrong partitions',
      F8: 'Batch insert partial failure silently drops records',
      F9: 'N+1 query in dashboard widget loading',
      F10: 'Deadlock from metric write lock ordering',

      // Alerting & Monitoring (G) - 8 bugs
      G1: 'Alert threshold comparison fails with float precision',
      G2: 'Anomaly detection baseline becomes stale',
      G3: 'Notification routing deduplication window too narrow',
      G4: 'Alert escalation timer race condition',
      G5: 'Metric aggregation cardinality explosion',
      G6: 'Alert silence window timezone handling incorrect',
      G7: 'Composite alert evaluation order wrong',
      G8: 'Alert recovery detection hysteresis missing',

      // Caching & Performance (H) - 8 bugs
      H1: 'Query result cache stampede on popular queries',
      H2: 'Dashboard cache key collision with different parameters',
      H3: 'Aggregation cache TTL race condition',
      H4: 'Connector state cache becomes stale',
      H5: 'TTL jitter missing causes thundering herd',
      H6: 'Write-through cache not atomic for metrics',
      H7: 'Pipeline config cache invalidation missing',
      H8: 'Hot partition detection has excessive lag',

      // Security (I) - 10 bugs
      I1: 'SQL injection in query API via unsanitized filter',
      I2: 'XSS in dashboard rendering via widget title',
      I3: 'SSRF in webhook connector URL validation',
      I4: 'Rate limit bypass via API key rotation',
      I5: 'CSRF in pipeline configuration endpoint',
      I6: 'Prototype pollution in transform config merge',
      I7: 'Path traversal in connector plugin upload',
      I8: 'ReDoS in data validation regex pattern',
      I9: 'NoSQL injection in alert filter expression',
      I10: 'IDOR on pipeline endpoints (missing tenant check)',

      // Scheduling (J) - 8 bugs
      J1: 'DAG execution topological sort produces wrong order',
      J2: 'Cron expression timezone mismatch',
      J3: 'Backfill job overlap detection fails',
      J4: 'Job retry exponential backoff overflows to negative',
      J5: 'Scheduler leader election split-brain',
      J6: 'Job dependency chain circular detection misses indirect cycles',
      J7: 'Parallel job resource limit not enforced',
      J8: 'Job cancellation leaves orphan tasks running',

      // Configuration (K) - 8 bugs
      K1: 'Pipeline config variable interpolation creates cycle',
      K2: 'Environment variable precedence order wrong',
      K3: 'Feature flag evaluation race condition',
      K4: 'Config version migration schema not applied',
      K5: 'Secret reference resolution uses eager instead of lazy eval',
      K6: 'Connector config merge uses shallow instead of deep merge',
      K7: 'Dynamic scaling threshold parsed as string not number',
      K8: 'Consul KV watch debounce race condition',

      // Observability (M) - 5 bugs
      M1: 'Trace context lost in stream processing pipeline',
      M2: 'Correlation ID not propagated across transform steps',
      M3: 'Metrics label cardinality explosion from pipeline IDs',
      M4: 'Health check aggregation reports wrong status',
      M5: 'Structured log field conflict in worker processes',
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
    return 'All 921 Jest tests must pass. Fix all 120 intentional bugs across 13 categories in 15 microservices.';
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

module.exports = DataNexusEnvironment;
