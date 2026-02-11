const test = require('node:test');
const assert = require('node:assert/strict');

const { projectedCost, marginRatio, budgetPressure } = require('../../src/core/economics');

test('projectedCost and marginRatio', () => {
  const cost = projectedCost(120, 145, 1.1);
  assert.equal(cost, 19140);
  assert.equal(marginRatio(22000, cost) > 0, true);
});

test('budgetPressure scales with backlog', () => {
  const pressure = budgetPressure(80, 100, 30);
  assert.equal(pressure, 1.1);
});
