/**
 * CloudMatrix RL Environment Setup
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
  'shared/clients/index.js': ['tests/unit/auth/permissions.test.js', 'tests/system/startup.test.js'],
  'shared/events/index.js': ['tests/system/startup.test.js', 'tests/chaos/distributed.test.js'],
  'shared/utils/index.js': ['tests/chaos/distributed.test.js', 'tests/system/startup.test.js'],
  'shared/realtime/index.js': ['tests/unit/realtime/sync.test.js', 'tests/unit/realtime/websocket.test.js'],

  // Gateway service
  'services/gateway/src/index.js': ['tests/integration/gateway.test.js'],
  'services/gateway/src/config.js': ['tests/system/startup.test.js'],
  'services/gateway/src/middleware/auth.js': ['tests/unit/auth/permissions.test.js', 'tests/integration/gateway.test.js'],
  'services/gateway/src/middleware/error.js': ['tests/integration/gateway.test.js'],
  'services/gateway/src/routes/index.js': ['tests/integration/gateway.test.js', 'tests/contract/api.test.js'],
  'services/gateway/src/services/registry.js': ['tests/system/startup.test.js'],

  // Auth service
  'services/auth/src/index.js': ['tests/integration/collaboration.test.js', 'tests/unit/auth/permissions.test.js'],
  'services/auth/src/services/auth.js': ['tests/unit/auth/permissions.test.js'],

  // Users service
  'services/users/src/index.js': ['tests/integration/collaboration.test.js'],

  // Documents service
  'services/documents/src/index.js': ['tests/integration/collaboration.test.js'],
  'services/documents/src/services/document.js': ['tests/unit/documents/processing.test.js', 'tests/integration/collaboration.test.js'],

  // Presence service
  'services/presence/src/index.js': ['tests/unit/realtime/websocket.test.js', 'tests/integration/collaboration.test.js'],
  'services/presence/src/services/presence.js': ['tests/unit/realtime/websocket.test.js', 'tests/unit/collaboration/features.test.js'],

  // Comments service
  'services/comments/src/index.js': ['tests/integration/collaboration.test.js'],

  // Versions service
  'services/versions/src/index.js': ['tests/integration/collaboration.test.js'],

  // Search service
  'services/search/src/index.js': ['tests/integration/search.test.js', 'tests/unit/search/indexing.test.js'],
  'services/search/src/services/search.js': ['tests/unit/search/indexing.test.js', 'tests/security/injection.test.js'],

  // Notifications service
  'services/notifications/src/index.js': ['tests/integration/collaboration.test.js'],

  // Storage service
  'services/storage/src/index.js': ['tests/integration/collaboration.test.js', 'tests/security/injection.test.js'],

  // Analytics service
  'services/analytics/src/index.js': ['tests/integration/collaboration.test.js'],

  // Billing service
  'services/billing/src/index.js': ['tests/unit/billing/subscription.test.js', 'tests/integration/collaboration.test.js'],
  'services/billing/src/services/subscription.js': ['tests/unit/billing/subscription.test.js'],

  // Permissions service
  'services/permissions/src/index.js': ['tests/unit/auth/permissions.test.js', 'tests/integration/collaboration.test.js'],
  'services/permissions/src/services/acl.js': ['tests/unit/auth/permissions.test.js'],

  // Webhooks service
  'services/webhooks/src/index.js': ['tests/integration/collaboration.test.js'],

  // Admin service
  'services/admin/src/index.js': ['tests/integration/collaboration.test.js'],
};

class CloudMatrixEnvironment {
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
            total: { type: 'Discrete', n: 900, description: 'Total test count' },
            passed: { type: 'Discrete', n: 900, description: 'Passing test count' },
            failed: { type: 'Discrete', n: 900, description: 'Failing test count' },
            pass_rate: { type: 'Box', low: 0.0, high: 1.0, shape: [1], description: 'Test pass rate' },
          },
        },
        step_count: { type: 'Discrete', n: 301, description: 'Current step number' },
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
    this.maxSteps = options.maxSteps || 300;
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
   */
  getTestsForFile(filePath) {
    if (this.fileTestMapping[filePath]) {
      return this.fileTestMapping[filePath];
    }

    const results = [];
    for (const [srcFile, testFiles] of Object.entries(this.fileTestMapping)) {
      if (filePath.startsWith(path.dirname(srcFile))) {
        results.push(...testFiles);
      }
    }

    return [...new Set(results)];
  }

  /**
   * Run targeted tests for specific file(s)
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
        reward: -0.01,
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
        const targeted = await this.runTargetedTests(relevantTests);
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
      L1: 'Circular import between shared modules (clients -> events -> utils -> realtime -> clients)',
      L2: 'RabbitMQ exchange not declared before binding queues',
      L3: 'Dead letter exchange not configured for failed messages',
      L4: 'Service discovery race condition on startup',
      L5: 'Package.json workspace conflict between shared and services',
      L6: 'Health check registration missing interval config',
      L7: 'Redis pub/sub channel naming collision between services',
      L8: 'Environment variable type coercion (PORT is string not number)',
      L9: 'WebSocket server bind race - missing await on initialization',
      L10: 'CORS preflight handler not responding to OPTIONS',
      L11: 'Logging transport initialization missing format',
      L12: 'Schema validation init - ajv not compiled before use',
      L13: 'Elasticsearch index mapping not created on startup',
      L14: 'Search index rebuild skips documents during reindex',
      L15: 'Worker registration happens before consumer channel ready',

      // Real-Time Sync (A) - 12 bugs
      A1: 'CRDT merge conflict on concurrent edit - wrong last-writer-wins',
      A2: 'Operational transform composition error - transforms not composed correctly',
      A3: 'Cursor position offset after insert - off by one in position calculation',
      A4: 'Selection range invalidation on delete - range not adjusted',
      A5: 'Undo/redo stack corruption in collaboration - shared stack polluted',
      A6: 'Real-time cursor jitter from debounce - wrong debounce timing',
      A7: 'Document state divergence on reconnect - missed operations not replayed',
      A8: 'Conflict resolution priority wrong - timestamp vs sequence number',
      A9: 'Transform function not commutative - different results depending on order',
      A10: 'Intention preservation lost - user intent not tracked through transforms',
      A11: 'Operation buffering overflow - unbounded buffer grows without limit',
      A12: 'Sync protocol version mismatch - no version negotiation',

      // WebSocket Management (B) - 10 bugs
      B1: 'Connection leak on abnormal close - socket not cleaned up',
      B2: 'Reconnection backoff not exponential - constant retry delay',
      B3: 'Presence state stale after disconnect - no cleanup on close',
      B4: 'Heartbeat interval too long - connection dropped before ping',
      B5: 'Message ordering not guaranteed over WebSocket',
      B6: 'Binary frame handling buffer overflow - no size check',
      B7: 'WebSocket authentication token expired - no refresh mechanism',
      B8: 'Room subscription memory leak - subscriptions not cleaned',
      B9: 'Broadcast fan-out slow path - sequential instead of parallel',
      B10: 'Connection pool exhaustion - no max connection limit',

      // Document Processing (C) - 8 bugs
      C1: 'Rich text delta merge conflict - concurrent format operations lost',
      C2: 'Embedded object serialization loss - nested objects stripped',
      C3: 'Table cell merge crash - null reference on merged cells',
      C4: 'Code block language detection regex DoS - catastrophic backtracking',
      C5: 'Image resize aspect ratio float precision - ratio calculation wrong',
      C6: 'Link preview URL validation SSRF - allows internal URLs',
      C7: 'Heading hierarchy enforcement gap - allows skipping levels',
      C8: 'List indentation level overflow - no max depth check',

      // Collaboration Features (D) - 10 bugs
      D1: 'Cursor tracking position drift - positions diverge over time',
      D2: 'Selection highlighting z-index conflict - overlapping highlights',
      D3: 'Co-editing cursor color collision - same color for different users',
      D4: 'Comment anchor invalidation on edit - anchors break when text changes',
      D5: 'Suggestion mode merge conflict - suggestions conflict with edits',
      D6: 'Track changes attribution wrong - changes attributed to wrong user',
      D7: 'Collaborative undo scope confusion - undoes other users operations',
      D8: 'Real-time notification ordering - notifications arrive out of order',
      D9: 'Presence indicator stale timeout - shows user as active when gone',
      D10: 'Collaborative lock escalation deadlock - two users lock same resource',

      // Search & Indexing (E) - 8 bugs
      E1: 'Full-text search injection - unsanitized query in Elasticsearch',
      E2: 'Indexing pipeline message loss - messages dropped without ack',
      E3: 'Faceted query aggregation overflow - integer overflow on large counts',
      E4: 'Search result permission filtering race - results shown before permission check',
      E5: 'Autocomplete suggestion cache stale - old suggestions served',
      E6: 'Index rebuild concurrent write conflict - writes during rebuild lost',
      E7: 'Search relevance scoring float precision - comparison fails on floats',
      E8: 'Multi-language tokenizer selection wrong - wrong analyzer for language',

      // Database & Transactions (F) - 10 bugs
      F1: 'Transaction isolation level wrong - read committed instead of serializable',
      F2: 'Connection pool exhaustion - connections not returned to pool',
      F3: 'Saga compensation rollback incomplete - partial compensation',
      F4: 'Outbox pattern message duplication - no dedup on outbox replay',
      F5: 'Read replica stale data - reading from replica before sync',
      F6: 'Optimistic locking concurrent retry - infinite retry loop',
      F7: 'Foreign key cascade delete race - parent deleted during child insert',
      F8: 'Batch insert partial failure silent - errors swallowed',
      F9: 'N+1 query in document listing - no eager loading',
      F10: 'Deadlock from inconsistent lock ordering - services lock in different order',

      // Auth & Permissions (G) - 8 bugs
      G1: 'JWT claims not validated properly - missing issuer/audience check',
      G2: 'OAuth state parameter CSRF - state not validated on callback',
      G3: 'Sharing link token collision - weak random token generation',
      G4: 'ACL inheritance evaluation order wrong - deny not checked first',
      G5: 'Permission cache invalidation race - stale permissions served',
      G6: 'Team role propagation delay - role change not reflected immediately',
      G7: 'Document-level permission check bypass - parent permission used',
      G8: 'Collaborative session token scope leak - token has too broad scope',

      // Caching & CDN (H) - 8 bugs
      H1: 'Cache stampede on popular document - no stampede protection',
      H2: 'Document snapshot cache stale - snapshot not invalidated on edit',
      H3: 'Search cache key collision - keys not unique enough',
      H4: 'CDN purge race on document update - purge before new version cached',
      H5: 'TTL jitter missing thundering herd - all caches expire simultaneously',
      H6: 'Write-through not atomic for metadata - partial write visible',
      H7: 'Edge cache inconsistency - different edges serve different versions',
      H8: 'LRU eviction during active collaboration - active docs evicted',

      // Security (I) - 10 bugs
      I1: 'SQL injection in search query parameter',
      I2: 'XSS in document rendering - HTML not sanitized',
      I3: 'SSRF in link preview - allows fetching internal URLs',
      I4: 'Rate limit bypass via WebSocket - WS not rate limited',
      I5: 'CSRF in sharing endpoints - no CSRF token validation',
      I6: 'Prototype pollution in document merge - Object.assign with user input',
      I7: 'Path traversal in file upload - filename not sanitized',
      I8: 'ReDoS in content search - catastrophic regex backtracking',
      I9: 'NoSQL injection in analytics filter - filter operators not sanitized',
      I10: 'Insecure direct object reference on versions - no authorization check',

      // Event Sourcing (J) - 8 bugs
      J1: 'Event ordering across partitions - no global sequence number',
      J2: 'Idempotency key collision - weak key generation',
      J3: 'Event replay skip on checkpoint - checkpoint position off by one',
      J4: 'Projection race condition - concurrent projections corrupt state',
      J5: 'Schema evolution deserialization fail - no migration for old events',
      J6: 'Tombstone compaction resurrects - deleted events reappear',
      J7: 'Snapshot corruption concurrent write - no write lock',
      J8: 'Event timestamp clock skew - events ordered by wall clock',

      // Configuration (K) - 8 bugs
      K1: 'Feature flag undefined not false - truthy check wrong',
      K2: 'JWT_SECRET validation missing - allows empty secret',
      K3: 'Rate limit string not parsed to int - string comparison',
      K4: 'WebSocket config type coercion - ping interval as string',
      K5: 'RabbitMQ prefetch string vs number - prefetch ignored',
      K6: 'Elasticsearch connection timeout default wrong - too short',
      K7: 'Redis cluster mode config - cluster options ignored',
      K8: 'Consul KV watch debounce race - updates missed',

      // Observability (M) - 5 bugs
      M1: 'Trace context lost in WebSocket handler - no propagation',
      M2: 'Correlation ID global state conflict - concurrent requests share ID',
      M3: 'Metrics cardinality explosion from document IDs - unbounded labels',
      M4: 'Health check false positive - reports healthy when DB down',
      M5: 'Structured log field collision - reserved field names used',
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
    return 'All 750+ Jest tests must pass. Fix all 120 intentional bugs across 13 categories in 15 microservices.';
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

module.exports = CloudMatrixEnvironment;
