const test = require('node:test');
const assert = require('node:assert/strict');
const { breachRisk, breachSeverity } = require('../../src/core/sla');

test('breachRisk respects buffer', () => {
  assert.equal(breachRisk(980, 1000, 30), true);
  assert.equal(breachRisk(930, 1000, 30), false);
});

test('breachSeverity categories are stable', () => {
  assert.equal(breachSeverity(900, 1000), 'none');
  assert.equal(breachSeverity(1200, 1000), 'minor');
  assert.equal(breachSeverity(1700, 1000), 'major');
  assert.equal(breachSeverity(2500, 1000), 'critical');
});
