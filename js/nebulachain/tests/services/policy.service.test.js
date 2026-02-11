const test = require('node:test');
const assert = require('node:assert/strict');
const policy = require('../../services/policy/service');

test('evaluatePolicyGate blocks high risk without MFA', () => {
  const result = policy.evaluatePolicyGate({ riskScore: 60, commsDegraded: false, hasMfa: false, priority: 5 });
  assert.equal(result.allowed, false);
});

test('enforceDualControl requires both operators', () => {
  assert.equal(policy.enforceDualControl(null, 'op2', 'deploy').authorized, false);
  assert.equal(policy.enforceDualControl('op1', 'op2', 'deploy').authorized, true);
});

test('riskBand classifies score correctly', () => {
  assert.equal(policy.riskBand(10), 'low');
  assert.equal(policy.riskBand(50), 'medium');
  assert.equal(policy.riskBand(90), 'critical');
});

test('computeComplianceScore returns weighted score', () => {
  const score = policy.computeComplianceScore({ incidentsResolved: 9, incidentsTotal: 10, slaMetPct: 80 });
  assert.ok(score > 0 && score <= 1.0);
});
