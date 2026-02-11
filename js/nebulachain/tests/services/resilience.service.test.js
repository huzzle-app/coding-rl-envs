const test = require('node:test');
const assert = require('node:assert/strict');
const resilience = require('../../services/resilience/service');

test('buildReplayPlan estimates time correctly', () => {
  const plan = resilience.buildReplayPlan({ eventCount: 100, timeoutS: 60, parallel: 2 });
  assert.ok(plan.estimatedS > 0);
  assert.equal(plan.steps, 100);
});

test('classifyReplayMode returns complete at full replay', () => {
  assert.equal(resilience.classifyReplayMode(100, 100), 'complete');
});

test('estimateReplayCoverage bounded by 1.0', () => {
  const coverage = resilience.estimateReplayCoverage({ steps: 20000 });
  assert.ok(coverage <= 1.0);
});

test('failoverPriority scores degraded regions', () => {
  const result = resilience.failoverPriority({ region: 'backup', isDegraded: true, latencyMs: 50 });
  assert.ok(typeof result.priority === 'number');
});
