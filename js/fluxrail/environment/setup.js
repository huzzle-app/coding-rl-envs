const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const reward = require('./reward');

const FILE_TEST_MAP = {
  'src/core/dispatch.js': ['tests/unit/dispatch.test.js', 'tests/integration/flow-orchestration.test.js'],
  'src/core/capacity.js': ['tests/unit/capacity.test.js', 'tests/integration/flow-orchestration.test.js'],
  'src/core/policy.js': ['tests/unit/policy.test.js', 'tests/integration/security-compliance.test.js'],
  'src/core/resilience.js': ['tests/unit/resilience.test.js', 'tests/integration/replay-chaos.test.js', 'tests/chaos/fault-injection.test.js'],
  'src/core/security.js': ['tests/unit/security.test.js', 'tests/integration/security-compliance.test.js'],
  'src/core/workflow.js': ['tests/unit/workflow.test.js', 'tests/integration/flow-orchestration.test.js'],
  'src/core/routing.js': ['tests/unit/routing.test.js', 'tests/chaos/network-partition.test.js'],
  'src/core/queue.js': ['tests/unit/queue.test.js', 'tests/chaos/fault-injection.test.js'],
  'src/core/statistics.js': ['tests/unit/statistics.test.js'],
  'src/core/sla.js': ['tests/unit/sla.test.js'],
  'src/core/ledger.js': ['tests/unit/ledger.test.js', 'tests/integration/economic-risk.test.js'],
  'src/core/economics.js': ['tests/unit/economics.test.js', 'tests/integration/economic-risk.test.js'],
  'src/core/authorization.js': ['tests/unit/authorization.test.js', 'tests/integration/security-compliance.test.js'],
  'src/core/replay.js': ['tests/unit/replay.test.js', 'tests/chaos/replay-storm.test.js', 'tests/integration/replay-chaos.test.js'],
  'src/core/dependency.js': ['tests/unit/dependency.test.js'],
  'src/models/': ['tests/unit/models.test.js', 'tests/integration/flow-orchestration.test.js'],
  'services/': ['tests/services/contracts.test.js'],
  'shared/': ['tests/services/contracts.test.js'],
  'migrations/': ['tests/services/contracts.test.js']
};

class FluxRailEnvironment {
  constructor(workDir) {
    this.workDir = workDir;
    this.stepCount = 0;
    this.maxSteps = 520;
    this.mutatingSteps = 0;
    this.fullRunInterval = 5;
    this.filesChanged = [];
    this.lastTestSummary = { total: 0, passed: 0, failed: 0, passRate: 0, targeted: false, output: '' };
  }

  safePath(rel) {
    if (!rel || rel.includes('..') || path.isAbsolute(rel)) throw new Error('invalid path');
    const root = path.resolve(this.workDir);
    const target = path.resolve(root, rel);
    if (!(target === root || target.startsWith(`${root}${path.sep}`))) throw new Error('path escapes workspace');
    return target;
  }

  validateAction(action) {
    const type = action.type;
    if (!['edit', 'read', 'run_command'].includes(type)) throw new Error('unknown action type');
    if (type === 'edit' || type === 'read') {
      const rel = String(action.file || '');
      this.safePath(rel);
      if (type === 'edit' && this.isTestPath(rel)) throw new Error('editing test files is not allowed');
      if (type === 'edit') {
        const content = String(action.content || '');
        if (content.length > 100000) throw new Error('content exceeds 100K character limit');
      }
    }
    if (type === 'run_command') {
      const parts = this.parseCommand(action.command);
      if (parts.length === 0) throw new Error('empty command');
      const allowed = new Set(['node', 'npm', 'cat', 'ls', 'grep', 'find', 'head', 'tail', 'wc']);
      if (!allowed.has(parts[0])) throw new Error('command not allowed');
    }
  }

  parseCommand(command) {
    const raw = String(command || '').trim();
    if (/[;&|`$><]/.test(raw)) throw new Error('unsupported shell metacharacters');
    return raw.split(/\s+/).filter(Boolean);
  }

  isTestPath(rel) {
    const normalized = String(rel).replace(/\\/g, '/');
    return normalized.startsWith('tests/')
      || normalized.includes('/tests/')
      || normalized.startsWith('__tests__/')
      || /\.(test|spec)\.[cm]?[jt]s$/i.test(normalized);
  }

  run(command) {
    const parts = this.parseCommand(command);
    if (parts.length === 0) throw new Error('empty command');
    return cp.execFileSync(parts[0], parts.slice(1), { cwd: this.workDir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  }

  edit(file, content) {
    const target = this.safePath(file);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content);
    this.filesChanged.push(file);
    return 'edit applied';
  }

  read(file) {
    return fs.readFileSync(this.safePath(file), 'utf8');
  }

  parseNodeTap(output, targeted) {
    const passed = (output.match(/^ok\s+/gm) || []).length;
    const failed = (output.match(/^not ok\s+/gm) || []).length;
    const total = passed + failed;
    const passRate = total > 0 ? passed / total : 0;
    return { total, passed, failed, passRate, targeted, output };
  }

  testsForFile(rel) {
    for (const [prefix, tests] of Object.entries(FILE_TEST_MAP)) {
      if (rel.startsWith(prefix)) return tests;
    }
    return [];
  }

  runFullTests() {
    let output = '';
    try {
      output = this.run('npm test');
    } catch (err) {
      output = `${err.stdout || ''}${err.stderr || ''}`;
    }
    return this.parseNodeTap(output, false);
  }

  runTargetedTests(rel) {
    const files = this.testsForFile(rel);
    if (files.length === 0) return { total: 0, passed: 0, failed: 0, passRate: 0, targeted: true, output: '' };
    let output = '';
    const command = `node --test --test-reporter tap ${files.join(' ')}`;
    try {
      output = this.run(command);
    } catch (err) {
      output = `${err.stdout || ''}${err.stderr || ''}`;
    }
    return this.parseNodeTap(output, true);
  }

  reset() {
    this.stepCount = 0;
    this.mutatingSteps = 0;
    this.filesChanged = [];
    this.lastTestSummary = this.runFullTests();
    return {
      observation: {
        action_result: '',
        step: 0,
        reward: 0,
        test_summary: {
          total: this.lastTestSummary.total,
          passed: this.lastTestSummary.passed,
          failed: this.lastTestSummary.failed,
          pass_rate: this.lastTestSummary.passRate,
          targeted: this.lastTestSummary.targeted
        }
      },
      reward: 0,
      done: false,
      info: {
        step: 0,
        max_steps: this.maxSteps,
        total_bugs: reward.totalBugs(),
        target_tests: reward.totalTests(),
        files_changed: [],
        pass_rate: this.lastTestSummary.passRate,
        tests_total: this.lastTestSummary.total,
        tests_failed: this.lastTestSummary.failed,
        targeted_run: this.lastTestSummary.targeted
      }
    };
  }

  step(action) {
    this.stepCount += 1;
    try {
      this.validateAction(action);
    } catch (err) {
      return {
        observation: { action_result: '', step: this.stepCount },
        reward: 0,
        done: this.stepCount >= this.maxSteps,
        info: { error: err.message, step: this.stepCount }
      };
    }

    const type = action.type;
    let result = '';
    let runError = null;

    try {
      if (type === 'edit') result = this.edit(action.file, action.content || '');
      else if (type === 'read') result = this.read(action.file);
      else result = this.run(action.command);
    } catch (err) {
      runError = err.message;
    }

    let summary = this.lastTestSummary;
    if (type === 'edit' || type === 'run_command') {
      this.mutatingSteps += 1;
      const targeted = type === 'edit' ? this.runTargetedTests(action.file) : { total: 0, passed: 0, failed: 0, passRate: 0, targeted: true, output: '' };
      if (targeted.total > 0 && this.mutatingSteps % this.fullRunInterval !== 0 && targeted.passRate < 1.0) summary = targeted;
      else summary = this.runFullTests();
    }

    const rewardValue = reward.sparseReward(summary.passRate);
    this.lastTestSummary = summary;
    const done = this.stepCount >= this.maxSteps || (!summary.targeted && summary.total > 0 && summary.passRate >= 1.0);

    const info = {
      step: this.stepCount,
      max_steps: this.maxSteps,
      total_bugs: reward.totalBugs(),
      target_tests: reward.totalTests(),
      files_changed: this.filesChanged,
      pass_rate: summary.passRate,
      tests_total: summary.total,
      tests_failed: summary.failed,
      targeted_run: summary.targeted
    };
    if (runError) info.error = runError;

    return {
      observation: {
        action_result: result,
        step: this.stepCount,
        reward: rewardValue,
        test_summary: {
          total: summary.total,
          passed: summary.passed,
          failed: summary.failed,
          pass_rate: summary.passRate,
          targeted: summary.targeted
        }
      },
      reward: rewardValue,
      done,
      info
    };
  }
}

module.exports = { FluxRailEnvironment };
