const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const reward = require('./reward');

const FILE_TEST_MAP = {
  'src/core/scheduling.js': ['tests/unit/scheduling.test.js', 'tests/integration/dispatch-flow.test.js'],
  'src/core/routing.js': ['tests/unit/routing.test.js', 'tests/integration/dispatch-flow.test.js'],
  'src/core/policy.js': ['tests/unit/policy.test.js', 'tests/integration/security-policy.test.js'],
  'src/core/security.js': ['tests/unit/security.test.js', 'tests/integration/security-policy.test.js'],
  'src/core/resilience.js': ['tests/unit/resilience.test.js', 'tests/integration/replay-chaos.test.js'],
  'src/core/queue.js': ['tests/unit/queue.test.js'],
  'src/core/statistics.js': ['tests/unit/statistics.test.js'],
  'src/core/workflow.js': ['tests/unit/workflow.test.js', 'tests/integration/dispatch-flow.test.js'],
  'src/models/': ['tests/unit/models.test.js'],
  'services/': ['tests/services/contracts.test.js'],
  'shared/': ['tests/services/contracts.test.js', 'tests/stress/cross-module-matrix.test.js'],
  'migrations/': ['tests/services/contracts.test.js']
};

class SignalDockEnvironment {
  constructor(workDir) {
    this.workDir = workDir;
    this.stepCount = 0;
    this.maxSteps = 320;
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

  run(command) {
    const parts = this.parseCommand(command);
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

  parseTap(output, targeted) {
    const passed = (output.match(/^ok\s+/gm) || []).length;
    const failed = (output.match(/^not ok\s+/gm) || []).length;
    const total = passed + failed;
    const passRate = total > 0 ? passed / total : 0;
    return { total, passed, failed, passRate, targeted, output };
  }

  testsForFile(rel) {
    for (const [prefix, tests] of Object.entries(FILE_TEST_MAP)) {
      if (rel.startsWith(prefix)) return [...new Set(tests)];
    }
    return [];
  }

  runFullTests() {
    let output = '';
    try { output = this.run('npm test'); } catch (err) { output = `${err.stdout || ''}${err.stderr || ''}`; }
    return this.parseTap(output, false);
  }

  runTargetedTests(rel) {
    const files = this.testsForFile(rel);
    if (files.length === 0) return { total: 0, passed: 0, failed: 0, passRate: 0, targeted: true, output: '' };
    let output = '';
    try { output = this.run(`node --test --test-reporter tap ${files.join(' ')}`); } catch (err) { output = `${err.stdout || ''}${err.stderr || ''}`; }
    return this.parseTap(output, true);
  }

  reset() {
    this.stepCount = 0;
    this.mutatingSteps = 0;
    this.filesChanged = [];
    this.lastTestSummary = this.runFullTests();
    const s = this.lastTestSummary;
    return {
      observation: { action_result: '', step: 0, reward: 0, test_summary: { total: s.total, passed: s.passed, failed: s.failed, pass_rate: s.passRate, targeted: s.targeted } },
      reward: 0,
      done: false,
      info: { step: 0, max_steps: this.maxSteps, total_bugs: reward.totalBugs(), target_tests: reward.totalTests(), files_changed: [], pass_rate: s.passRate, tests_total: s.total, tests_failed: s.failed, targeted_run: s.targeted }
    };
  }

  step(action) {
    this.stepCount += 1;
    try { this.validateAction(action); } catch (err) {
      return { observation: { action_result: '', step: this.stepCount }, reward: 0, done: this.stepCount >= this.maxSteps, info: { error: err.message, step: this.stepCount } };
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

    this.lastTestSummary = summary;
    const rewardValue = reward.sparseReward(summary.passRate);
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
      observation: { action_result: result, step: this.stepCount, reward: rewardValue, test_summary: { total: summary.total, passed: summary.passed, failed: summary.failed, pass_rate: summary.passRate, targeted: summary.targeted } },
      reward: rewardValue,
      done,
      info
    };
  }
}

module.exports = { SignalDockEnvironment };
