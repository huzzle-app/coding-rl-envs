const test = require('node:test');
const assert = require('node:assert/strict');

const { projectedCost, marginRatio } = require('../../src/core/economics');
const { evaluatePolicy } = require('../../src/core/policy');

test('economic pressure and policy risk integrate', () => {
  const cost = projectedCost(260, 145, 1.15);
  const margin = marginRatio(cost + 60_000, cost);
  const decision = evaluatePolicy({ securityIncidents: 1, backlog: 40, staleMinutes: 3, margin });
  assert.equal(decision.allow, true);
  assert.equal(decision.score > 0, true);
});
