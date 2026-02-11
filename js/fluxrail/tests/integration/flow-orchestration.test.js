const test = require('node:test');
const assert = require('node:assert/strict');
const { chooseRoute } = require('../../src/core/dispatch');
const { rebalance } = require('../../src/core/capacity');
const { overrideAllowed } = require('../../src/core/policy');
const { transitionAllowed } = require('../../src/core/workflow');

test('dispatch + capacity + policy flow', () => {
  const route = chooseRoute({ north: 18, west: 22 });
  const admitted = rebalance(12, 8, 3);
  const override = overrideAllowed('committee approved expedited dispatch', 2, 45);

  assert.equal(route, 'north');
  assert.equal(admitted, 8);
  assert.equal(override, true);
  assert.equal(transitionAllowed('capacity_checked', 'dispatched'), true);
});
